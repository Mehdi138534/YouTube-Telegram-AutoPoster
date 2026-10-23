#!/usr/bin/env python3
"""Publish new public YouTube uploads to a Telegram channel."""
from __future__ import annotations

import html
import json
import logging
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("youtube-telegram")

API = "https://www.googleapis.com/youtube/v3"
STATE_FILE = Path(os.getenv("STATE_FILE", "state.json"))
HANDLE = os.getenv("YOUTUBE_HANDLE", "Sir_Mr_yellow138").lstrip("@").strip()
YOUTUBE_URL = os.getenv("YOUTUBE_URL", f"https://www.youtube.com/@{HANDLE}")
TELEGRAM_URL = os.getenv("TELEGRAM_URL", "https://t.me/Sirmryellow138")
INITIAL_POST_LIMIT = max(0, int(os.getenv("INITIAL_POST_LIMIT", "3")))
MAX_ITEMS = max(1, min(50, int(os.getenv("MAX_ITEMS", "15"))))
MAX_POSTS_PER_RUN = max(1, int(os.getenv("MAX_POSTS_PER_RUN", "5")))
MAX_AGE_DAYS = max(1, int(os.getenv("MAX_AGE_DAYS", "14")))
HTTP = requests.Session()


class BotError(RuntimeError):
    pass


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise BotError(f"Required environment variable {name} is missing")
    return value


def youtube_json(resource: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = HTTP.get(f"{API}/{resource}", params=params, timeout=30)
    except requests.RequestException as exc:
        raise BotError(f"YouTube API network error ({resource}): {exc}") from exc
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not response.ok or "error" in data:
        error = data.get("error", {})
        details = error.get("message") or response.text[:300] or "unknown response"
        reason = ""
        errors = error.get("errors") or []
        if errors:
            reason = f" ({errors[0].get('reason', 'API error')})"
        raise BotError(f"YouTube API {resource} failed: HTTP {response.status_code}{reason}: {details}")
    return data


def telegram(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = required_env("TELEGRAM_BOT_TOKEN")
    try:
        response = HTTP.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=40)
    except requests.RequestException as exc:
        raise BotError(f"Telegram {method} network error: {exc}") from exc
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not response.ok or not data.get("ok"):
        description = data.get("description") or response.text[:300] or "unknown response"
        code = data.get("error_code", response.status_code)
        raise BotError(f"Telegram {method} failed ({code}): {description}")
    return data.get("result") or {}


def default_state() -> dict[str, Any]:
    return {"posted_ids": [], "initialized": False, "intro_posted": False}


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return default_state()
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or not isinstance(state.get("posted_ids", []), list):
            raise ValueError("unexpected state format")
        normalized = default_state()
        normalized.update(state)
        # Preserve order while removing legacy duplicates.
        normalized["posted_ids"] = list(dict.fromkeys(str(x) for x in normalized["posted_ids"]))
        return normalized
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise BotError(f"Cannot read state file {STATE_FILE}: {exc}") from exc


def save_state(state: dict[str, Any]) -> None:
    state["posted_ids"] = list(dict.fromkeys(state.get("posted_ids", [])))[-5000:]
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace prevents a partial JSON file if the runner exits mid-write.
    fd, tmp_name = tempfile.mkstemp(prefix=f".{STATE_FILE.name}.", dir=str(STATE_FILE.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(state, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, STATE_FILE)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def append_seen(state: dict[str, Any], video_id: str) -> None:
    if video_id not in state["posted_ids"]:
        state["posted_ids"].append(video_id)


def get_uploads_playlist(api_key: str) -> str:
    result = youtube_json("channels", {"part": "snippet,contentDetails", "forHandle": HANDLE, "key": api_key})
    items = result.get("items", [])
    if not items:
        raise BotError(f"YouTube channel @{HANDLE} was not found. Check YOUTUBE_HANDLE and API key.")
    try:
        return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    except (KeyError, TypeError) as exc:
        raise BotError("YouTube API did not return the uploads playlist for this channel") from exc


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fetch_videos(api_key: str, playlist_id: str) -> list[dict[str, Any]]:
    playlist = youtube_json("playlistItems", {
        "part": "snippet,contentDetails", "playlistId": playlist_id,
        "maxResults": MAX_ITEMS, "key": api_key,
    })
    ids = []
    for item in playlist.get("items", []):
        video_id = (item.get("contentDetails") or {}).get("videoId")
        if video_id and video_id not in ids:
            ids.append(video_id)
    if not ids:
        return []
    details = youtube_json("videos", {"part": "snippet,contentDetails,status", "id": ",".join(ids), "key": api_key})
    by_id = {item.get("id"): item for item in details.get("items", []) if item.get("id")}
    videos = []
    for video_id in ids:  # playlist order is newest first
        item = by_id.get(video_id)
        if not item:
            continue
        snippet = item.get("snippet") or {}
        status = item.get("status") or {}
        live_status = snippet.get("liveBroadcastContent", "none")
        published = parse_datetime(snippet.get("publishedAt"))
        if status.get("privacyStatus") not in (None, "public"):
            continue
        if live_status in ("live", "upcoming"):
            log.info("Skipping %s: broadcast status is %s", video_id, live_status)
            continue
        if not published or published > datetime.now(timezone.utc) + timedelta(minutes=2):
            log.info("Skipping %s: not published yet", video_id)
            continue
        item["_published"] = published
        videos.append(item)
    return sorted(videos, key=lambda v: v["_published"], reverse=True)


def is_probable_short(video: dict[str, Any]) -> bool:
    """Shorts classification is heuristic: YouTube's public API has no Shorts flag."""
    snippet = video.get("snippet") or {}
    title = snippet.get("title", "")
    tags = " ".join(snippet.get("tags", []) or [])
    text = f"{title} {tags}"
    explicit = bool(re.search(r"(?:^|\s)#shorts?(?:\s|$)", text, flags=re.I))
    duration = (video.get("contentDetails") or {}).get("duration")
    seconds = None
    if duration:
        match = re.fullmatch(r"P(?:\d+D)?T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?", duration)
        if match:
            hours, minutes, secs = (float(value or 0) for value in match.groups())
            seconds = hours * 3600 + minutes * 60 + secs
    return explicit or (seconds is not None and 0 < seconds <= 180)


def thumbnail_url(video: dict[str, Any]) -> str | None:
    thumbnails = (video.get("snippet") or {}).get("thumbnails") or {}
    for key in ("maxres", "standard", "high", "medium", "default"):
        url = (thumbnails.get(key) or {}).get("url")
        if url:
            return url
    return None


def video_url(video: dict[str, Any]) -> str:
    short = is_probable_short(video)
    return f"https://www.youtube.com/{'shorts/' if short else 'watch?v='}{video['id']}"


def build_caption(video: dict[str, Any]) -> str:
    title = (video.get("snippet") or {}).get("title") or "ویدیوی جدید"
    short = is_probable_short(video)
    prefix = (
        "⚡️ رفیق، یه شورت تازه رسید! 😎\nچند ثانیه بیا کنارمون؛ دیدنت کلی انرژی می‌ده 💛🤝"
        if short else
        "🎬 رفقای بامرام، ویدیوی جدیدمون منتشر شد!\nمثل همیشه دمتون گرم که کنارمونین ❤️"
    )
    label = "📱 شورت جدید" if short else "🍿 ویدیوی جدید"
    # Keep ample headroom for Telegram's entity parsing and UTF-16 length rules.
    title = title[:120]
    caption = f"{prefix}\n\n{label}\n🎥 <b>{html.escape(title, quote=False)}</b>\n\nاگه دیدیش، نظرت رو برامون بنویس؛ حمایتت کلی انرژی می‌ده 🌱🫶"
    plain = re.sub(r"<[^>]+>", "", caption)
    plain = html.unescape(plain)
    if len(plain.encode("utf-16-le")) // 2 > 1024 or len(caption) > 1024:
        raise BotError("Caption length guard failed")
    return caption


def post_keyboard(video: dict[str, Any]) -> dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🍿 پخشش کن!", "url": video_url(video)}],
        [{"text": "📺 کانال یوتیوب Sir Mr Yellow", "url": YOUTUBE_URL}],
    ]}


def publish(video: dict[str, Any], chat_id: str) -> None:
    caption = build_caption(video)
    payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML", "reply_markup": post_keyboard(video)}
    photo = thumbnail_url(video)
    if photo:
        try:
            telegram("sendPhoto", {**payload, "photo": photo})
            return
        except BotError as exc:
            # Only retry a definite bad-photo response. Network/429/server failures may
            # have reached Telegram already, so falling back could create duplicate posts.
            if "failed (400)" not in str(exc):
                raise
            log.warning("Thumbnail rejected; trying text post instead: %s", exc)
    telegram("sendMessage", {"chat_id": chat_id, "text": caption, "parse_mode": "HTML",
                              "disable_web_page_preview": False, "reply_markup": post_keyboard(video)})


def main() -> None:
    api_key = required_env("YOUTUBE_API_KEY")
    chat_id = required_env("TELEGRAM_CHAT_ID")
    state = load_state()
    playlist_id = get_uploads_playlist(api_key)
    videos = fetch_videos(api_key, playlist_id)
    log.info("Found %d eligible public uploads", len(videos))
    known = set(state["posted_ids"])
    candidates = [v for v in videos if v["id"] not in known]
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

    if not state.get("initialized"):
        eligible = [v for v in candidates if v["_published"] >= cutoff]
        chosen = eligible[:INITIAL_POST_LIMIT]
        ignored = [v for v in candidates if v not in chosen]
        # Persist skipped old/excess items before attempting posts, but keep initialized false
        # so a failed first-run post is picked up again next run.
        for video in ignored:
            append_seen(state, video["id"])
        save_state(state)
        log.info("First run: publishing up to %d newest eligible video(s)", len(chosen))
    else:
        chosen = [v for v in candidates if v["_published"] >= cutoff]
        for video in candidates:
            if video["_published"] < cutoff:
                append_seen(state, video["id"])
        save_state(state)

    sent = 0
    for video in reversed(chosen):  # publish oldest first, including first run
        if sent >= MAX_POSTS_PER_RUN:
            break
        publish(video, chat_id)
        append_seen(state, video["id"])
        save_state(state)  # commit each successful post before moving on
        sent += 1
        log.info("Published %s: %s", video["id"], (video.get("snippet") or {}).get("title", ""))

    # First-run candidates beyond the per-run cap must not be marked seen; they'll be picked up next run.
    state["initialized"] = True
    save_state(state)
    log.info("Done. Published %d new video(s).", sent)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.error("Bot stopped: %s", exc)
        sys.exit(1)
