import requests
import os
import json
import time


BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


SUBREDDIT = "GreekDick"

REDDIT_URL = f"https://www.reddit.com/r/GreekDick/new.json?limit=10"


SEEN_FILE = "seen.json"


HEADERS = {
    "User-Agent": "telegram-reddit-bot/1.0"
}


def load_seen():

    if os.path.exists(SEEN_FILE):

        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))

    return set()



def save_seen(seen):

    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)



def telegram_request(method, data):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    r = requests.post(url, data=data)

    print(r.text)



def send_photo(photo, caption):

    telegram_request(
        "sendPhoto",
        {
            "chat_id": CHAT_ID,
            "photo": photo,
            "caption": caption
        }
    )



def send_message(text):

    telegram_request(
        "sendMessage",
        {
            "chat_id": CHAT_ID,
            "text": text
        }
    )



def get_image(post):

    try:

        if "preview" in post:

            images = post["preview"]["images"]

            if images:

                return (
                    images[0]
                    ["source"]
                    ["url"]
                    .replace("&amp;", "&")
                )


        if post.get("thumbnail","").startswith("http"):

            return post["thumbnail"]


    except Exception:
        pass


    return None



def main():

    print("BOT STARTED")


    seen = load_seen()


    r = requests.get(
        REDDIT_URL,
        headers=HEADERS
    )


    if r.status_code != 200:

        print(
            "Reddit error:",
            r.status_code
        )

        return



    data = r.json()


    posts = data["data"]["children"]



    for item in reversed(posts):


        post = item["data"]


        post_id = post["id"]


        if post_id in seen:
            continue



        title = post.get(
            "title",
            ""
        )


        author = post.get(
            "author",
            "unknown"
        )


        permalink = (
            "https://reddit.com"
            +
            post.get(
                "permalink",
                ""
            )
        )


        caption = (
            "📌 Reddit\n"
            f"👤 u/{author}\n\n"
            f"{title}\n\n"
            f"🔗 {permalink}"
        )


        print(
            "Checking:",
            title
        )



        image = get_image(post)



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

            send_message(
                caption
            )



        seen.add(post_id)



    save_seen(seen)



if __name__ == "__main__":

    main()
