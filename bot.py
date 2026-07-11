import feedparser
import requests
import os
import subprocess
import json
import time

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

RSS_URL = "https://www.reddit.com/r/unknown/.rss"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SEEN_FILE = "seen.json"

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": text
    })

def send_photo(url_photo, caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "photo": url_photo,
        "caption": caption
    })

def send_video(url_video, caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "video": url_video,
        "caption": caption
    })

def extract_video(url):
    try:
        result = subprocess.run(
            ["yt-dlp", "-g", url],
            capture_output=True,
            text=True
        )
        video_url = result.stdout.strip().split("\n")[0]
        if video_url.startswith("http"):
            return video_url
    except:
        return None
    return None

def get_image(entry):
    if "media_content" in entry:
        return entry.media_content[0]["url"]
    if "links" in entry:
        for l in entry.links:
            if "image" in l.type:
                return l.href
    return None

def run():
    seen = load_seen()

    feed = feedparser.parse(RSS_URL)

    for entry in feed.entries[:10]:
        post_id = entry.id

        if post_id in seen:
            continue

        title = entry.title
        link = entry.link
        author = entry.author

        caption = f"{title}\n👤 {author}\n{link}"

        print("Checking:", title)

        # 1️⃣ Try image
        img = get_image(entry)
        if img:
            print("Sending photo:", img)
            send_photo(img, caption)
            seen.add(post_id)
            continue

        # 2️⃣ Try video
        video = extract_video(link)
        if video:
            print("Sending video:", video)
            send_video(video, caption)
            seen.add(post_id)
            continue

        print("No media found")

    save_seen(seen)


if __name__ == "__main__":
    run()
