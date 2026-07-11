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


SUBREDDIT = "GreekDick"

RSS_URL = f"https://www.reddit.com/r/GreekDick/.rss"


SEEN_FILE = "seen.json"


MAX_VIDEO_SIZE = 190 * 1024 * 1024



HEADERS = {
    "User-Agent": "Mozilla/5.0 RedditTelegramBot"
}



def load_seen():

    if os.path.exists(SEEN_FILE):

        try:

            with open(SEEN_FILE, "r") as f:

                return set(json.load(f))

        except:

            pass


    return set()



def save_seen(seen):

    with open(SEEN_FILE, "w") as f:

        json.dump(
            list(seen),
            f
        )



def telegram_request(method, data=None, files=None):

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/{method}"
    )


    while True:

        try:

            r = requests.post(
                url,
                data=data,
                files=files,
                timeout=60
            )


            result = r.json()


        except Exception as e:

            print(
                "Telegram error:",
                e
            )

            return None



        if result.get("error_code") == 429:

            wait = result["parameters"]["retry_after"]

            print(
                "Telegram wait:",
                wait
            )

            time.sleep(wait)

            continue



        print(result)

        return result




def get_reddit_json(url):

    try:

        r = requests.get(

            url.rstrip("/") + ".json",

            headers=HEADERS,

            timeout=20

        )


        if r.status_code == 200:

            return r.json()



        print(
            "Reddit error:",
            r.status_code
        )


    except Exception as e:

        print(
            "Reddit JSON:",
            e
        )


    return None

def extract_gallery(post_url):

    images = []


    data = get_reddit_json(
        post_url
    )


    if not data:

        return images



    try:

        post = data[0]["data"]["children"][0]["data"]


        gallery = post.get(
            "gallery_data"
        )


        metadata = post.get(
            "media_metadata"
        )



        if gallery and metadata:


            for item in gallery["items"]:


                media_id = item["media_id"]



                if media_id in metadata:


                    media = metadata[media_id]



                    if "p" in media:

                        url = media["p"][-1]["u"]

                    else:

                        url = media["s"]["u"]



                    url = url.replace(
                        "&amp;",
                        "&"
                    )


                    images.append(
                        url
                    )


    except Exception as e:

        print(
            "Gallery error:",
            e
        )


    return images




def extract_media(entry):


    # Πρώτα ελέγχουμε gallery

    gallery = extract_gallery(
        entry.link
    )


    if gallery:

        return gallery




    text = entry.description.replace(
        "&amp;",
        "&"
    )



    urls = re.findall(
        r'https?://[^\s"<>]+',
        text
    )



    media = []



    for url in urls:



        # Redgifs μόνο watch links

        if (
            "redgifs.com" in url
            and "/watch/" in url
        ):

            media.append(
                url
            )



        # Reddit εικόνες / video

        elif (
            "i.redd.it" in url
            or "v.redd.it" in url
        ):

            media.append(
                url
            )




    # αφαίρεση duplicates

    clean = []

    seen = set()



    for url in media:


        name = url.split("/")[-1].split("?")[0]



        if name not in seen:

            clean.append(
                url
            )

            seen.add(
                name
            )



    return clean




def is_video(url):

    return (

        "v.redd.it" in url

        or "redgifs.com/watch" in url

        or url.endswith(".gif")

        or ".gif?" in url

    )




def download_file(url):

    try:

        url = url.replace(
            "&amp;",
            "&"
        )


        r = requests.get(

            url,

            headers=HEADERS,

            timeout=60

        )


        if r.status_code == 200:


            ext = ".jpg"



            if ".png" in url:

                ext = ".png"



            f = tempfile.NamedTemporaryFile(

                delete=False,

                suffix=ext

            )


            f.write(
                r.content
            )


            f.close()


            return f.name



    except Exception as e:

        print(
            "Download image:",
            e
        )



    return None




def download_video(url):

    folder = tempfile.mkdtemp()


    try:


        print(
            "Downloading video:",
            url
        )



        subprocess.run(

            [

                "yt-dlp",

                "-f",

                "best[ext=mp4]/best",

                "-o",

                f"{folder}/video.%(ext)s",

                url

            ],

            stdout=subprocess.DEVNULL,

            stderr=subprocess.DEVNULL,

            timeout=180

        )



        files = glob.glob(
            folder + "/*"
        )


        if files:

            return files[0]



    except Exception as e:

        print(
            "yt-dlp error:",
            e
        )


    return None

def send_photo(path, caption):

    try:

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


    except Exception as e:

        print(
            "Photo send error:",
            e
        )




def send_video(path, caption):


    size = os.path.getsize(
        path
    )


    print(
        "Video size:",
        size
    )



    if size > MAX_VIDEO_SIZE:

        print(
            "Video over 190MB - skipped"
        )

        return



    try:

        with open(path, "rb") as f:


            telegram_request(

                "sendVideo",

                data={

                    "chat_id": CHAT_ID,

                    "caption": caption,

                    "supports_streaming": True

                },

                files={

                    "video": f

                }

            )


    except Exception as e:

        print(
            "Video send error:",
            e
        )





def send_album(paths, caption):


    if len(paths) > 10:

        paths = paths[:10]



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



        media.append(
            item
        )


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


    print(
        "BOT STARTED"
    )


    seen = load_seen()



    feed = feedparser.parse(
        RSS_URL
    )


    print(
        "Posts found:",
        len(feed.entries)
    )



    for entry in reversed(feed.entries):


        if entry.id in seen:

            continue



        print(
            "Checking:",
            entry.title
        )



        media = extract_media(
            entry
        )



        if not media:


            print(
                "No media - skip"
            )


            seen.add(
                entry.id
            )

            continue




        author = getattr(

            entry,

            "author",

            "unknown"

        )



        caption = (

            "📌 Reddit\n"

            f"👤 {author}\n\n"

            f"{entry.title}\n\n"

            f"🔗 {entry.link}"

        )



        photos = []

        videos = []



        for item in media:



            if is_video(item):


                video = download_video(
                    item
                )


                if video:

                    videos.append(
                        video
                    )



            else:


                image = download_file(
                    item
                )


                if image:

                    photos.append(
                        image
                    )




        if len(photos) > 1:


            print(
                "Gallery:",
                len(photos)
            )


            send_album(
                photos,
                caption
            )



        elif len(photos) == 1:


            send_photo(
                photos[0],
                caption
            )



        for video in videos:


            send_video(
                video,
                caption
            )



        for file in photos + videos:


            try:

                os.remove(
                    file
                )

            except:

                pass



        seen.add(
            entry.id
        )


        time.sleep(5)



    save_seen(
        seen
    )





if __name__ == "__main__":

    main()
