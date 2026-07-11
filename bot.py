import feedparser
import requests
import os
import json


BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


RSS_URL = "https://www.reddit.com/r/GreekDick/.rss"

SEEN_FILE = "seen.json"


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))

    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def send_photo(url, caption):

    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    r = requests.post(
        api,
        data={
            "chat_id": CHAT_ID,
            "photo": url,
            "caption": caption
        }
    )

    print(r.text)


def send_message(text):

    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    r = requests.post(
        api,
        data={
            "chat_id": CHAT_ID,
            "text": text
        }
    )

    print(r.text)



def main():

    print("BOT STARTED")

    seen = load_seen()

    feed = feedparser.parse(RSS_URL)


    for post in feed.entries[:10]:

        if post.id in seen:
            continue


        title = post.title
        link = post.link
        user = post.author


        caption = (
            f"📌 Reddit\n"
            f"👤 u/{user}\n\n"
            f"{title}\n\n"
            f"🔗 {link}"
        )


        print("Found:", title)


        # αρχικά στέλνουμε το link
        send_message(caption)


        seen.add(post.id)



    save_seen(seen)



if __name__ == "__main__":
    main()
