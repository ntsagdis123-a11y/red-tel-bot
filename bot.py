import requests
import feedparser
import os
import json
import re
import tempfile
import time
import subprocess
import glob


BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# FIX: ήταν "SUBREDDIT" (placeholder) - βάλε το πραγματικό subreddit,
# είτε hardcoded είτε μέσω env var.
SUBREDDIT = os.getenv("GreekDick", "pics")

RSS_URL = f"https://www.reddit.com/r/GreekDick/.rss"

SEEN_FILE = "seen.json"

MAX_VIDEO_SIZE = 190 * 1024 * 1024
MAX_ALBUM_SIZE = 10  # Telegram sendMediaGroup limit

HEADERS = {
    "User-Agent": "Mozilla/5.0 RedditTelegramBot"
}


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()


def save_seen(seen):
    # FIX: γράφουμε σε προσωρινό αρχείο και μετά κάνουμε rename,
    # ώστε ένα crash στη μέση του write να μη χαλάσει το seen.json
    tmp_path = SEEN_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(list(seen), f)
    os.replace(tmp_path, SEEN_FILE)


def telegram_request(method, data=None, files=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    while True:
        try:
            r = requests.post(url, data=data, files=files, timeout=60)
        except requests.exceptions.RequestException as e:
            # FIX: πριν, ένα network error εδώ θα έκανε crash όλο το script
            print("Telegram network error:", e)
            time.sleep(5)
            continue

        try:
            result = r.json()
        except Exception:
            print(r.text)
            return None

        if result.get("error_code") == 429:
            wait = result.get("parameters", {}).get("retry_after", 5)
            print("Telegram wait:", wait)
            time.sleep(wait)
            continue

        if not result.get("ok"):
            print("Telegram error:", result)

        return result


def get_reddit_json(url):
    try:
        r = requests.get(url.rstrip("/") + ".json", headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("JSON error:", e)
    return None


def download(url):
    try:
        url = url.replace("&amp;", "&")

        r = requests.get(url, headers=HEADERS, timeout=40)

        if r.status_code == 200:
            ext = ".jpg"
            # FIX: έλεγχος με βάση το path της url (χωρίς query string)
            # ώστε να μην μπερδεύεται από παραμέτρους στο url
            path = url.split("?")[0].lower()

            if path.endswith(".png"):
                ext = ".png"
            elif path.endswith(".gif"):
                ext = ".gif"
            elif path.endswith(".webp"):
                ext = ".webp"

            f = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            f.write(r.content)
            f.close()
            return f.name

    except Exception as e:
        print("Download error:", e)

    return None


def extract_gallery(post_url):
    images = []

    # FIX: πριν καλούσαμε get_reddit_json για ΚΑΘΕ post (ακόμα και μη-gallery),
    # ρίχνοντας άχρηστα requests στο reddit. Τώρα το κάνουμε μόνο αν η url
    # μοιάζει με gallery post.
    if "/gallery/" not in post_url:
        return images

    data = get_reddit_json(post_url)
    if not data:
        return images

    try:
        post = data[0]["data"]["children"][0]["data"]
        gallery = post.get("gallery_data")
        metadata = post.get("media_metadata")

        if gallery and metadata:
            for item in gallery["items"]:
                mid = item["media_id"]

                if mid in metadata:
                    meta = metadata[mid]

                    # gallery item can be an image ("s": {"u": ...})
                    # or a video/gif ("s": {"gif": ...} or {"mp4": ...})
                    s = meta.get("s", {})

                    if "u" in s:
                        url = s["u"].replace("&amp;", "&").replace("preview.", "i.")
                        images.append(url)
                    elif "mp4" in s:
                        # FIX: πριν αγνοούνταν τα video items μέσα σε galleries
                        url = s["mp4"].replace("&amp;", "&")
                        images.append(url)

    except Exception as e:
        print("Gallery error:", e)

    return images


def is_video_url(url):
    # FIX: πριν, το v.redd.it (reddit-hosted video) δεν αναγνωριζόταν σαν video
    # και κατέβαινε λάθος σαν "εικόνα" .jpg μέσω download().
    lowered = url.lower()
    return (
        "redgifs.com" in lowered
        or "v.redd.it" in lowered
        or "/video/" in lowered
        or lowered.split("?")[0].endswith(".mp4")
        or lowered.split("?")[0].endswith(".gifv")
    )


def extract_media(entry):
    media = []

    gallery = extract_gallery(entry.link)
    if gallery:
        return gallery

    # FIX: entry.description μπορεί να μην υπάρχει σε κάποια entries
    text = getattr(entry, "description", "") or ""
    text = text.replace("&amp;", "&")

    urls = re.findall(r'https?://[^"\s<>]+', text)

    for u in urls:
        if "redd.it" in u or "redgifs.com" in u:
            media.append(u)

    return media


def download_video(url):
    folder = tempfile.mkdtemp()

    try:
        command = [
            "yt-dlp",
            "-f",
            "bestvideo+bestaudio/best",
            "--merge-output-format",
            "mp4",
            "-o",
            f"{folder}/video.%(ext)s",
            url
        ]

        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=180
        )

        files = glob.glob(folder + "/*")

        if files:
            return files[0]

    except Exception as e:
        print("yt-dlp error:", e)

    return None


def send_photo(path, caption):
    with open(path, "rb") as f:
        telegram_request(
            "sendPhoto",
            data={"chat_id": CHAT_ID, "caption": caption},
            files={"photo": f}
        )


def send_video(path, caption):
    size = os.path.getsize(path)

    if size > MAX_VIDEO_SIZE:
        print("Video too large:", size)
        return

    with open(path, "rb") as f:
        telegram_request(
            "sendVideo",
            data={"chat_id": CHAT_ID, "caption": caption, "supports_streaming": True},
            files={"video": f}
        )


def send_album(paths, caption):
    # FIX: Telegram sendMediaGroup δέχεται max 10 media ανά κλήση.
    # Πριν, ένα gallery με >10 items θα έκανε την κλήση να αποτύχει σιωπηλά.
    for chunk_start in range(0, len(paths), MAX_ALBUM_SIZE):
        chunk = paths[chunk_start:chunk_start + MAX_ALBUM_SIZE]

        media = []
        files = {}

        for i, path in enumerate(chunk):
            key = f"photo{i}"
            item = {"type": "photo", "media": f"attach://{key}"}

            if i == 0 and chunk_start == 0:
                item["caption"] = caption

            media.append(item)
            files[key] = open(path, "rb")

        telegram_request(
            "sendMediaGroup",
            data={"chat_id": CHAT_ID, "media": json.dumps(media)},
            files=files
        )

        for f in files.values():
            f.close()


def process_entry(entry, seen):
    title = entry.title

    author = getattr(entry, "author", "unknown").replace("u/", "")

    caption = (
        "📌 Reddit\n"
        f"👤 u/{author}\n\n"
        f"{title}\n\n"
        f"🔗 {entry.link}"
    )

    print("Checking:", title)

    media = extract_media(entry)

    if not media:
        print("No media - skip")
        seen.add(entry.id)
        return

    downloaded = []
    videos = []

    for item in media:
        if is_video_url(item):
            print("Video:", item)
            video = download_video(item)
            if video:
                videos.append(video)
        else:
            file = download(item)
            if file:
                downloaded.append(file)

    if len(downloaded) > 1:
        print("Sending gallery:", len(downloaded))
        send_album(downloaded, caption)
    elif len(downloaded) == 1:
        send_photo(downloaded[0], caption)

    for video in videos:
        send_video(video, caption)

    for f in downloaded + videos:
        try:
            os.remove(f)
        except Exception:
            pass

    seen.add(entry.id)


def main():
    print("BOT STARTED")

    # FIX: αν λείπουν τα credentials, καλύτερα να σταματήσουμε αμέσως
    # με σαφές μήνυμα αντί να αποτυγχάνει κάθε telegram_request χωρίς εξήγηση.
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: BOT_TOKEN or CHAT_ID env vars are missing.")
        return

    seen = load_seen()

    feed = feedparser.parse(RSS_URL)

    for entry in reversed(feed.entries):
        if entry.id in seen:
            continue

        # FIX: αν ένα entry ρίξει exception (π.χ. broken download),
        # πριν σταματούσε ΟΛΟ το loop. Τώρα συνεχίζει στα επόμενα entries.
        try:
            process_entry(entry, seen)
        except Exception as e:
            print("Error processing entry:", entry.id, e)

        # FIX: αποθηκεύουμε seen μετά από κάθε entry (όχι μόνο στο τέλος),
        # ώστε ένα crash στη μέση να μη χάνει την ήδη γινομένη πρόοδο.
        save_seen(seen)

        time.sleep(5)

    save_seen(seen)


if __name__ == "__main__":
    main()
