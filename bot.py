import requests
import feedparser
import os
import json
import re


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



def telegram(method, data):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    r = requests.post(
        url,
        data=data
    )

    print(r.text)



def send_photo(url, caption):

    telegram(
        "sendPhoto",
        {
            "chat_id": CHAT_ID,
            "photo": url,
            "caption": caption
        }
    )



def send_album(images, caption):

    media = []

    for index, image in enumerate(images):

        item = {
            "type": "photo",
            "media": image
        }

        # caption μόνο στην πρώτη φωτογραφία
        if index == 0:
            item["caption"] = caption

        media.append(item)


    telegram(
        "sendMediaGroup",
        {
            "chat_id": CHAT_ID,
            "media": json.dumps(media)
        }
    )



def extract_images(entry):

    description = entry.description.replace("&amp;", "&")

    images = []


    # preview.redd.it
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



    # i.redd.it
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


        post_id = entry.id


        if post_id in seen:
            continue



        title = entry.title


        author = "unknown"


        if hasattr(entry, "author"):
            author = entry.author



        caption = (
            "📌 Reddit\n"
            f"👤 u/{author}\n\n"
            f"{title}\n\n"
            f"🔗 {entry.link}"
        )



        print("Checking:", title)



        images = extract_images(entry)



        if len(images) > 1:

            print(
                "Gallery found:",
                len(images),
                "images"
            )

            send_album(
                images,
                caption
            )


        elif len(images) == 1:

            print(
                "Image found:",
                images[0]
            )

            send_photo(
                images[0],
                caption
            )


        else:

            print("No image")

            telegram(
                "sendMessage",
                {
                    "chat_id": CHAT_ID,
                    "text": caption
                }
            )



        seen.add(post_id)



    save_seen(seen)



if __name__ == "__main__":
    main()
