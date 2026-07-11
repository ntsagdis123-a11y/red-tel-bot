import requests
import feedparser
import os
import json
import re
import tempfile


BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SUBREDDIT = "videos"

RSS_URL = f"https://www.reddit.com/r/GreekDick/.rss"

SEEN_FILE = "seen.json"



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

    r = requests.post(
        url,
        data=data,
        files=files
    )

    print(r.text)

    return r.json()



def download_image(url):

    try:

        r = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        if r.status_code == 200:

            suffix = ".jpg"

            if "png" in r.headers.get("content-type",""):
                suffix = ".png"


            file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix
            )

            file.write(r.content)
            file.close()

            return file.name


    except Exception as e:

        print(
            "Download error:",
            e
        )


    return None



def send_photo(path, caption):

    with open(path, "rb") as photo:

        telegram_request(
            "sendPhoto",
            data={
                "chat_id": CHAT_ID,
                "caption": caption
            },
            files={
                "photo": photo
            }
        )



def send_album(paths, caption):

    media = []

    files = {}


    for i, path in enumerate(paths):

        key = f"photo{i}"

        media.append(
            {
                "type": "photo",
                "media": f"attach://{key}",
                **({"caption": caption} if i == 0 else {})
            }
        )

        files[key] = open(path, "rb")



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



def extract_images(entry):

    description = entry.description.replace("&amp;", "&")

    images = []


    found = re.findall(
        r'https://preview\.redd\.it/[^"\s<>]+',
        description
    )


    for img in found:

        img = img.replace("&amp;", "&")

        img = re.sub(
            r'width=\d+',
            'width=1080',
            img
        )

        if img not in images:
            images.append(img)



    found = re.findall(
        r'https://i\.redd\.it/[^"\s<>]+',
        description
    )


    for img in found:

        img = img.replace("&amp;", "&")

        if img not in images:
            images.append(img)



    return images



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


        image_urls = extract_images(entry)


        downloaded = []


        for url in image_urls:

            file = download_image(url)

            if file:

                downloaded.append(file)



        if len(downloaded) > 1:

            print(
                "Sending gallery:",
                len(downloaded)
            )

            send_album(
                downloaded,
                caption
            )


        elif len(downloaded) == 1:

            print(
                "Sending image"
            )

            send_photo(
                downloaded[0],
                caption
            )


        else:

            print(
                "No image"
            )

            telegram_request(
                "sendMessage",
                data={
                    "chat_id": CHAT_ID,
                    "text": caption
                }
            )



        for file in downloaded:

            try:
                os.remove(file)

            except:
                pass



        seen.add(entry.id)



    save_seen(seen)



if __name__ == "__main__":

    main()
