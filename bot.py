import html
import json
import os
import sys
from pathlib import Path

import requests

YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CHANNEL_HANDLE = os.getenv("YOUTUBE_HANDLE", "Sir_Mr_yellow138").lstrip("@")
STATE_FILE = Path("state.json")
INITIAL_POST_LIMIT = int(os.getenv("INITIAL_POST_LIMIT", "3"))
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "15"))
API_BASE = "https://www.googleapis.com/youtube/v3"
TG_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def get_json(url, params=None):
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", "API request failed"))
    return data


def telegram(method, payload):
    response = requests.post(f"{TG_BASE}/{method}", json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data}")
    return data["result"]


def get_channel():
    data = get_json(f"{API_BASE}/channels", {
        "part": "snippet,contentDetails",
        "forHandle": CHANNEL_HANDLE,
        "key": YOUTUBE_API_KEY,
    })
    items = data.get("items", [])
    if not items:
        raise RuntimeError(
            f"Channel @{CHANNEL_HANDLE} was not found. Check YOUTUBE_HANDLE and API key."
        )
    channel = items[0]
    return channel["contentDetails"]["relatedPlaylists"]["uploads"]


def get_latest_videos(uploads_playlist):
    data = get_json(f"{API_BASE}/playlistItems", {
        "part": "snippet,contentDetails",
        "playlistId": uploads_playlist,
        "maxResults": min(MAX_ITEMS, 50),
        "key": YOUTUBE_API_KEY,
    })
    items = data.get("items", [])
    ids = [x.get("contentDetails", {}).get("videoId") for x in items]
    ids = [x for x in ids if x]
    if not ids:
        return []

    details = get_json(f"{API_BASE}/videos", {
        "part": "snippet,contentDetails",
        "id": ",".join(ids),
        "key": YOUTUBE_API_KEY,
    })
    by_id = {v["id"]: v for v in details.get("items", [])}
    videos = []
    # Keep the playlist's newest-first ordering.
    for item in items:
        vid = item.get("contentDetails", {}).get("videoId")
        if vid in by_id:
            videos.append(by_id[vid])
    return videos


def parse_duration_seconds(duration):
    # ISO 8601 duration such as PT1M23S or PT45S.
    import re
    match = re.fullmatch(
        r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?",
        duration or ""
    )
    if not match:
        return 0
    days, hours, minutes, seconds = (int(x or 0) for x in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def content_label(video):
    duration = parse_duration_seconds(video.get("contentDetails", {}).get("duration"))
    title = video.get("snippet", {}).get("title", "")
    # YouTube Shorts can be up to 3 minutes; this is a practical guess,
    # not a definitive Shorts classification from the API.
    if duration <= 180 or "#shorts" in title.lower():
        return "📱 احتمالاً Shorts"
    return "🎬 ویدیوی لانگ"


def thumbnail_url(snippet):
    thumbs = snippet.get("thumbnails", {})
    for key in ("maxres", "standard", "high", "medium", "default"):
        if thumbs.get(key, {}).get("url"):
            return thumbs[key]["url"]
    return None


def load_state():
    if not STATE_FILE.exists():
        return {"posted_ids": [], "initialized": False}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data.get("posted_ids"), list):
            raise ValueError("Invalid posted_ids")
        return data
    except Exception as exc:
        raise RuntimeError(f"Could not read {STATE_FILE}: {exc}") from exc


def save_state(state):
    # Keep a bounded history so the state file stays small.
    state["posted_ids"] = state.get("posted_ids", [])[-5000:]
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def publish(video):
    vid = video["id"]
    snippet = video.get("snippet", {})
    title = html.escape(snippet.get("title", "ویدیوی جدید"))
    url = f"https://www.youtube.com/watch?v={vid}"
    duration = parse_duration_seconds(video.get("contentDetails", {}).get("duration"))
    # The public API does not provide a definitive Shorts flag; use a practical heuristic.
    is_short = duration <= 180 or "#shorts" in snippet.get("title", "").lower()

    if is_short:
        intro = (
            "⚡️ رفیق، یه شورت تازه رسید! 😎\n"
            "چند ثانیه بیا کنارمون؛ دیدنت کلی انرژی می‌ده 💛🤝"
        )
        label = "📱 شورت جدید"
    else:
        intro = (
            "🎬 رفقای بامرام، ویدیوی جدیدمون منتشر شد!\n"
            "مثل همیشه دمتون گرم که کنارمونین؛ با حمایت شما با قدرت ادامه می‌دیم ❤️"
        )
        label = "🍿 ویدیوی لانگ جدید"

    caption = (
        f"{intro}\n\n"
        f"{label}\n"
        f"🎥 <b>{title}</b>\n\n"
        "اگه دیدیش، نظرت رو برام بنویس؛ اگه هم خوشت اومد با یه رفیق به اشتراک بذار. "
        "هوای همو داریم، مرام همین چیزاست 🌱🫶\n\n"
        f'<a href="{url}">▶️ بزن بریم تماشا</a>\n\n'
        "ممنون که عضوی از این جمعی رفیق 💛"
    )
    if len(caption) > 1000:
        caption = caption[:990] + "…"

    thumb = thumbnail_url(snippet)
    if thumb:
        try:
            telegram("sendPhoto", {
                "chat_id": TELEGRAM_CHAT_ID,
                "photo": thumb,
                "caption": caption,
                "parse_mode": "HTML",
            })
            return
        except Exception as exc:
            print(f"Thumbnail post failed; falling back to text: {exc}")
    telegram("sendMessage", {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": caption,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })

def main():
    state = load_state()
    posted = set(state.get("posted_ids", []))
    uploads_playlist = get_channel()
    videos = get_latest_videos(uploads_playlist)

    if not state.get("initialized"):
        # On the very first run, only publish the newest N items, then mark
        # the rest of the fetched items as seen to avoid flooding the channel.
        chosen = videos[:max(0, INITIAL_POST_LIMIT)]
        skip = videos[max(0, INITIAL_POST_LIMIT):]
        for video in skip:
            posted.add(video["id"])
        state["initialized"] = True
        save_state({"posted_ids": list(posted), "initialized": True})
        print(f"First run: publishing up to {len(chosen)} newest video(s).")
    else:
        chosen = [video for video in videos if video["id"] not in posted]
        chosen.reverse()  # older new items first if multiple arrived between runs

    sent = 0
    for video in chosen:
        vid = video["id"]
        if vid in posted:
            continue
        publish(video)
        posted.add(vid)
        save_state({"posted_ids": list(posted), "initialized": True})
        sent += 1
        print(f"Published: {vid} - {video.get('snippet', {}).get('title', '')}")

    # Persist even if there was nothing new.
    save_state({"posted_ids": list(posted), "initialized": True})
    print(f"Done. Published {sent} new video(s).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
