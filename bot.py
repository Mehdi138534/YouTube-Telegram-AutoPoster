import html
import json
import os
import re
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
MAX_STATE_IDS = 5000
SHORT_MAX_SECONDS = 60
CAPTION_LIMIT = 1024  # Telegram caption limit (characters, after parsing)
API_BASE = "https://www.googleapis.com/youtube/v3"
TG_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _check(response, what):
    """Raise an error that says what failed and why, including the API's own message."""
    if response.ok:
        return response.json()
    try:
        body = response.json()
    except ValueError:
        body = response.text[:300]
    raise RuntimeError(f"{what} failed with HTTP {response.status_code}: {body}")


def get_json(url, params=None, what="YouTube API request"):
    response = requests.get(url, params=params, timeout=30)
    data = _check(response, what)
    if "error" in data:
        raise RuntimeError(f"{what} error: {data['error'].get('message', data['error'])}")
    return data


def telegram(method, payload):
    response = requests.post(f"{TG_BASE}/{method}", json=payload, timeout=30)
    data = _check(response, f"Telegram {method}")
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} rejected: {data.get('description', data)}")
    return data["result"]


def get_channel():
    data = get_json(f"{API_BASE}/channels", {
        "part": "snippet,contentDetails",
        "forHandle": CHANNEL_HANDLE,
        "key": YOUTUBE_API_KEY,
    }, what="YouTube channel lookup")
    items = data.get("items", [])
    if not items:
        raise RuntimeError(
            f"Channel @{CHANNEL_HANDLE} not found. Check YOUTUBE_HANDLE and the API key."
        )
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def get_latest_videos(uploads_playlist):
    data = get_json(f"{API_BASE}/playlistItems", {
        "part": "snippet,contentDetails",
        "playlistId": uploads_playlist,
        "maxResults": min(MAX_ITEMS, 50),
        "key": YOUTUBE_API_KEY,
    }, what="YouTube playlist lookup")
    items = data.get("items", [])
    ids = [x.get("contentDetails", {}).get("videoId") for x in items]
    ids = [x for x in ids if x]
    if not ids:
        return []

    details = get_json(f"{API_BASE}/videos", {
        "part": "snippet,contentDetails,liveStreamingDetails",
        "id": ",".join(ids),
        "key": YOUTUBE_API_KEY,
    }, what="YouTube video details lookup")
    by_id = {v["id"]: v for v in details.get("items", [])}

    videos = []
    for vid in ids:  # playlist order is newest-first and is preserved here
        if vid in by_id:
            videos.append(by_id[vid])
    return videos


def is_not_ready(video):
    """Upcoming premieres and scheduled lives are skipped until they actually go live or upload.
    They are not marked as posted, so they get picked up on a later run.
    """
    status = video.get("snippet", {}).get("liveBroadcastContent", "none")
    return status in ("upcoming", "live")


def duration_seconds(video):
    raw = video.get("contentDetails", {}).get("duration", "")
    match = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", raw)
    if not match:
        return None
    days, hours, minutes, seconds = (int(g or 0) for g in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def is_short(video):
    """The public API has no Shorts flag. Heuristic: #shorts in the title, or a very short duration."""
    title = video.get("snippet", {}).get("title", "").lower()
    if "#shorts" in title:
        return True
    seconds = duration_seconds(video)
    return seconds is not None and 0 < seconds <= SHORT_MAX_SECONDS


def thumbnail_url(snippet):
    thumbs = snippet.get("thumbnails", {})
    for key in ("maxres", "standard", "high", "medium", "default"):
        if thumbs.get(key, {}).get("url"):
            return thumbs[key]["url"]
    return None


def load_state():
    if not STATE_FILE.exists():
        return {"posted_ids": [], "initialized": False, "intro_posted": False}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse {STATE_FILE}: {exc}") from exc
    if not isinstance(data.get("posted_ids", []), list):
        raise RuntimeError(f"{STATE_FILE} has an invalid posted_ids field")
    data.setdefault("posted_ids", [])
    data.setdefault("initialized", False)
    data.setdefault("intro_posted", False)
    return data


def save_state(state):
    # Keep order (oldest first) and drop the oldest entries when over the cap.
    state["posted_ids"] = list(dict.fromkeys(state.get("posted_ids", [])))[-MAX_STATE_IDS:]
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_caption(video):
    snippet = video.get("snippet", {})
    vid = video["id"]
    short = is_short(video)
    url = f"https://www.youtube.com/shorts/{vid}" if short else f"https://www.youtube.com/watch?v={vid}"

    # Trim the raw title before escaping so no HTML entity or tag is ever cut in half.
    raw_title = snippet.get("title", "ویدیوی جدید").strip()
    if len(raw_title) > 150:
        raw_title = raw_title[:147].rstrip() + "..."
    title = html.escape(raw_title)

    if short:
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
        label = "🍿 ویدیوی جدید"

    caption = (
        f"{intro}\n\n"
        f"{label}\n"
        f"🎥 <b>{title}</b>\n\n"
        "اگه دیدیش، نظرت رو برام بنویس؛ اگه هم خوشت اومد با یه لایک و ساب. "
        "مارو همراهی کن 🌱🫶\n\n"
        f'<a href="{url}">▶️ بزن بریم تماشا</a>\n\n'
        "ممنون که عضوی از این جمعی رفیق 💛"
    )
    if len(caption) > CAPTION_LIMIT:
        raise RuntimeError(f"Caption is too long ({len(caption)} chars) for video {vid}")
    return caption


def publish(video):
    caption = build_caption(video)
    thumb = thumbnail_url(video.get("snippet", {}))
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
            print(f"Thumbnail post failed, falling back to text: {exc}")

    telegram("sendMessage", {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": caption,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })


def main():
    state = load_state()
    posted = list(dict.fromkeys(state.get("posted_ids", [])))
    posted_set = set(posted)

    uploads_playlist = get_channel()
    videos = [v for v in get_latest_videos(uploads_playlist) if not is_not_ready(v)]

    if not state.get("initialized"):
        chosen = videos[:max(0, INITIAL_POST_LIMIT)]
        for video in videos[max(0, INITIAL_POST_LIMIT):]:
            if video["id"] not in posted_set:
                posted.append(video["id"])
                posted_set.add(video["id"])
        state["initialized"] = True
        state["posted_ids"] = posted
        save_state(state)
        print(f"First run: publishing up to {len(chosen)} newest video(s).")
    else:
        chosen = [video for video in videos if video["id"] not in posted_set]
        chosen.reverse()  # oldest unseen first

    sent = 0
    for video in chosen:
        vid = video["id"]
        if vid in posted_set:
            continue
        publish(video)  # if this raises, state for earlier videos is already saved
        posted.append(vid)
        posted_set.add(vid)
        state["posted_ids"] = posted
        save_state(state)
        sent += 1
        print(f"Published: {vid} - {video.get('snippet', {}).get('title', '')}")

    print(f"Done. Published {sent} new video(s).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
