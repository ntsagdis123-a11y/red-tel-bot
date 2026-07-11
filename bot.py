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


    except Exception as e:

        print(
            "JSON error:",
            e
        )


    return None



def download(url):

    try:

        url = url.replace(
            "&amp;",
            "&"
        )


        r = requests.get(
            url,
            headers=HEADERS,
            timeout=40
        )


        if r.status_code == 200:


            ext=".jpg"


            if ".png" in url:
                ext=".png"


            if ".gif" in url:
                ext=".gif"


            f=tempfile.NamedTemporaryFile(
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
            "Download error:",
            e
        )


    return None



def extract_gallery(post_url):

    images=[]


    data=get_reddit_json(
        post_url
    )


    if not data:
        return images



    try:

        post=data[0]["data"]["children"][0]["data"]


        gallery=post.get(
            "gallery_data"
        )


        metadata=post.get(
            "media_metadata"
        )


        if gallery and metadata:


            for item in gallery["items"]:


                mid=item["media_id"]


                if mid in metadata:


                    url=metadata[mid]["s"]["u"]


                    url=url.replace(
                        "&amp;",
                        "&"
                    )


                    url=url.replace(
                        "preview.",
                        "i."
                    )


                    images.append(url)



    except Exception as e:

        print(
            "Gallery error:",
            e
        )


    return images



def extract_media(entry):

    media=[]


    # gallery

    gallery=extract_gallery(
        entry.link
    )


    if gallery:
        return gallery



    text=entry.description.replace(
        "&amp;",
        "&"
    )


    urls=re.findall(
        r'https?://[^"\s<>]+',
        text
    )


    for u in urls:


        if (
            "redd.it" in u
            or "redgifs.com" in u
        ):

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

    with open(path,"rb") as f:

        telegram_request(
            "sendPhoto",
            data={
                "chat_id":CHAT_ID,
                "caption":caption
            },
            files={
                "photo":f
            }
        )



def send_video(path, caption):

    size=os.path.getsize(path)


    if size > MAX_VIDEO_SIZE:

        print(
            "Video too large:",
            size
        )

        return



    with open(path,"rb") as f:

        telegram_request(
            "sendVideo",
            data={
                "chat_id":CHAT_ID,
                "caption":caption,
                "supports_streaming":True
            },
            files={
                "video":f
            }
        )



def send_album(paths, caption):

    media=[]
    files={}


    for i,path in enumerate(paths):

        key=f"photo{i}"


        item={
            "type":"photo",
            "media":f"attach://{key}"
        }


        if i==0:

            item["caption"]=caption


        media.append(item)


        files[key]=open(
            path,
            "rb"
        )



    telegram_request(
        "sendMediaGroup",
        data={
            "chat_id":CHAT_ID,
            "media":json.dumps(media)
        },
        files=files
    )



    for f in files.values():
        f.close()



def main():

    print(
        "BOT STARTED"
    )


    seen=load_seen()


    feed=feedparser.parse(
        RSS_URL
    )



    for entry in reversed(feed.entries):


        if entry.id in seen:
            continue



        title=entry.title


        author=getattr(
            entry,
            "author",
            "unknown"
        ).replace(
            "u/",
            ""
        )



        caption=(

            "📌 Reddit\n"
            f"👤 u/{author}\n\n"
            f"{title}\n\n"
            f"🔗 {entry.link}"

        )


        print(
            "Checking:",
            title
        )



        media=extract_media(
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



        downloaded=[]


        videos=[]



        for item in media:


            if (
                "redgifs.com" in item
                or "/video/" in item
            ):

                print(
                    "Video:",
                    item
                )


                video=download_video(
                    item
                )


                if video:
                    videos.append(video)



            else:


                file=download(
                    item
                )


                if file:
                    downloaded.append(file)



        if len(downloaded)>1:

            print(
                "Sending gallery:",
                len(downloaded)
            )

            send_album(
                downloaded,
                caption
            )


        elif len(downloaded)==1:

            send_photo(
                downloaded[0],
                caption
            )



        for video in videos:

            send_video(
                video,
                caption
            )



        for f in downloaded + videos:

            try:

                os.remove(f)

            except:

                pass



        seen.add(
            entry.id
        )


        time.sleep(5)



    save_seen(
        seen
    )



if __name__=="__main__":

    main()    
