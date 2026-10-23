import html
import os
from pathlib import Path
import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
YOUTUBE_URL = os.getenv("YOUTUBE_URL", "https://www.youtube.com/@Sir_Mr_yellow138")
TELEGRAM_URL = os.getenv("TELEGRAM_URL", "https://t.me/Sirmryellow138")
STATE_FILE = Path("state.json")
TG_BASE = f"https://api.telegram.org/bot{TOKEN}"


def telegram(method, payload):
    r = requests.post(f"{TG_BASE}/{method}", json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data}")
    return data["result"]


def load_state():
    if not STATE_FILE.exists():
        return {"posted_ids": [], "initialized": False, "intro_posted": False}
    data = __import__("json").loads(STATE_FILE.read_text(encoding="utf-8"))
    data.setdefault("posted_ids", [])
    data.setdefault("initialized", False)
    data.setdefault("intro_posted", False)
    return data


def save_state(state):
    STATE_FILE.write_text(
        __import__("json").dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main():
    state = load_state()
    if state.get("intro_posted") and os.getenv("FORCE_INTRO", "0") != "1":
        print("Intro is already marked as posted. Nothing to do.")
        return

    text = (
        "💛 سلام رفیق! به جمع Sir Mr Yellow خوش اومدی!\n\n"
        "این بات رفیق کوچیکه‌ی کانالمونه؛ هر وقت ویدیوی جدیدی روی یوتیوب منتشر بشه، "
        "اینجا هم خبرش رو می‌ذاریم که چیزی رو از دست ندی. 🎬🔥\n\n"
        "🎥 کانال یوتیوب:\n"
        f'<a href="{html.escape(YOUTUBE_URL, quote=True)}">Sir Mr Yellow</a>\n\n'
        "📢 کانال تلگرام:\n"
        f'<a href="{html.escape(TELEGRAM_URL, quote=True)}">Sirmryellow138</a>\n\n'
        "دمت گرم که کنارمونی رفیق 💛\n"
        "هوای همو داریم؛ مرام همین چیزاست 🤝"
    )
    result = telegram("sendMessage", {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })
    state["intro_posted"] = True
    state["intro_message_id"] = result.get("message_id")
    save_state(state)
    print(f"Intro published: message_id={result.get('message_id')}")


if __name__ == "__main__":
    main()
