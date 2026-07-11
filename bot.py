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



def send_message(text):

    telegram(
        "sendMessage",
        {
            "chat_id": CHAT_ID,
            "text": text
        }
    )



def extract_image(entry):

    description = entry.description.replace("&amp;", "&")


    images = re.findall(
        r'https://preview\.redd\.it/[^"\s<>]+',
        description
    )


    if images:

        return images[0]


    images = re.findall(
        r'https://i\.redd\.it/[^"\s<>]+',
        description
    )


    if images:

        return images[0]


    return None



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



        link = entry.link



        caption = (
            "📌 Reddit\n"
            f"👤 u/{author}\n\n"
            f"{title}\n\n"
            f"🔗 {link}"
        )



        print(
            "Checking:",
            title
        )



        image = extract_image(entry)



        if image:

            print(
                "Image found:",
                image
            )

            send_photo(
                image,
                caption
            )

        else:

            print(
                "No image"
            )

            send_message(
                caption
            )



        seen.add(post_id)



    save_seen(seen)



if __name__ == "__main__":

    main()
