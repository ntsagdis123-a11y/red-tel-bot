import requests
import feedparser
import os
import json
import re
import tempfile
import time


BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SUBREDDIT = "GreekDick"

RSS_URL = f"https://www.reddit.com/r/GreekDick/.rss"

SEEN_FILE = "seen.json"


HEADERS = {
    "User-Agent": "Mozilla/5.0 RedditTelegramBot"
}


def load_seen():

    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))

    return set()



def save_seen(seen):

    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)



def telegram_request(method, data=None, files=None):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"


    while True:

        r = requests.post(
            url,
            data=data,
            files=files
        )


        try:
            result = r.json()

        except:
            print(r.text)
            return None



        if result.get("error_code") == 429:

            wait = result["parameters"]["retry_after"]

            print(
                f"Telegram limit. Waiting {wait}s"
            )

            time.sleep(wait)

            continue


        print(result)

        return result



def download_file(url):

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )


        if r.status_code == 200:

            f = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".jpg"
            )

            f.write(r.content)
            f.close()

            return f.name


    except Exception as e:

        print(
            "Download error:",
            e
        )


    return None



def get_reddit_json(url):

    try:

        r = requests.get(
            url.rstrip("/") + ".json",
            headers=HEADERS,
            timeout=15
        )

        if r.status_code == 200:
            return r.json()


    except Exception as e:

        print(
            "JSON error:",
            e
        )


    return None



def extract_gallery(post_url):

    images = []


    data = get_reddit_json(post_url)


    if not data:
        return images



    try:

        post = data[0]["data"]["children"][0]["data"]


        gallery = post.get("gallery_data")


        media = post.get("media_metadata")


        if gallery and media:


            for item in gallery["items"]:

                media_id = item["media_id"]


                if media_id in media:

                    img = media[media_id]["s"]["u"]

                    img = img.replace(
                        "&amp;",
                        "&"
                    )

                    images.append(img)


    except Exception as e:

        print(
            "Gallery error:",
            e
        )


    return images



def extract_single_image(entry):

    text = entry.description.replace(
        "&amp;",
        "&"
    )


    found = re.findall(
        r'https://(?:preview\.redd\.it|i\.redd\.it)/[^"\s<>]+',
        text
    )


    if found:

        return found[0]


    return None



def send_photo(path, caption):

    with open(path, "rb") as f:

        telegram_request(
            "sendPhoto",
            data={
                "chat_id": CHAT_ID,
                "caption": caption
            },
            files={
                "photo": f
            }
        )



def send_album(paths, caption):

    media = []
    files = {}


    for i, path in enumerate(paths):

        key = f"photo{i}"

        item = {
            "type": "photo",
            "media": f"attach://{key}"
        }


        if i == 0:
            item["caption"] = caption


        media.append(item)

        files[key] = open(
            path,
            "rb"
        )



    telegram_request(
        "sendMediaGroup",
        data={
            "chat_id": CHAT_ID,
            "media": json.dumps(media)
        },
        files=files
    )


    for f in files.values():
        f.close()



def main():

    print("BOT STARTED")


    seen = load_seen()


    feed = feedparser.parse(
        RSS_URL
    )


    for entry in reversed(feed.entries):


        if entry.id in seen:
            continue



        title = entry.title


        author = getattr(
            entry,
            "author",
            "unknown"
        )


        author = author.replace(
            "u/",
            ""
        )



        caption = (
            "📌 Reddit\n"
            f"👤 u/{author}\n\n"
            f"{title}\n\n"
            f"🔗 {entry.link}"
        )


        print(
            "Checking:",
            title
        )



        images = extract_gallery(
            entry.link
        )


        if not images:


            img = extract_single_image(
                entry
            )


            if img:
                images.append(img)



        downloaded = []


        for img in images:

            file = download_file(
                img
            )

            if file:
                downloaded.append(file)



        if len(downloaded) > 1:

            print(
                "Gallery:",
                len(downloaded)
            )

            send_album(
                downloaded,
                caption
            )


        elif len(downloaded) == 1:

            print(
                "Image"
            )

            send_photo(
                downloaded[0],
                caption
            )


        else:

            telegram_request(
                "sendMessage",
                data={
                    "chat_id": CHAT_ID,
                    "text": caption
                }
            )



        for f in downloaded:

            try:
                os.remove(f)

            except:
                pass



        seen.add(entry.id)


        time.sleep(5)



    save_seen(seen)



if __name__ == "__main__":
    main()
