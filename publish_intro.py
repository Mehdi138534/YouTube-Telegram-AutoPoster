import html
import os
from pathlib import Path
import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
YOUTUBE_URL = os.getenv(
    "YOUTUBE_URL",
    "https://www.youtube.com/@Sir_Mr_yellow138"
)
TELEGRAM_URL = os.getenv(
    "TELEGRAM_URL",
    "https://t.me/Sirmryellow138"
)
STATE_FILE = Path("state.json")
TG_BASE = f"https://api.telegram.org/bot{TOKEN}"


def telegram(method, payload):
    r = requests.post(
        f"{TG_BASE}/{method}",
        json=payload,
        timeout=30
    )
    r.raise_for_status()
    data = r.json()

    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data}")

    return data["result"]


def load_state():
    if not STATE_FILE.exists():
        return {
            "posted_ids": [],
            "initialized": False,
            "intro_posted": False
        }

    data = __import__("json").loads(
        STATE_FILE.read_text(encoding="utf-8")
    )

    data.setdefault("posted_ids", [])
    data.setdefault("initialized", False)
    data.setdefault("intro_posted", False)

    return data


def save_state(state):
    STATE_FILE.write_text(
        __import__("json").dumps(
            state,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8",
    )


def main():
    state = load_state()

    if state.get("intro_posted") and os.getenv("FORCE_INTRO", "0") != "1":
        print("Intro is already marked as posted. Nothing to do.")
        return

    text = (
        "🤖 <b>من کی‌ام؟</b>\n\n"
        "سلام رفیق! 👋💛\n\n"
        "من باتِ <b>Sir Mr Yellow</b> ـم؛ اومدم که نذارم هیچ "
        "ویدیوی جدیدی از رفیقت از دستت در بره! 😎🔥\n\n"
        
        "کار من خیلی ساده‌ست:\n\n"
        
        "🎬 هر وقت توی کانال یوتیوب <b>Sir Mr Yellow</b> "
        "یه ویدیوی جدید منتشر بشه، من می‌رم سراغش و خبرشو "
        "توی کانال تلگرام می‌ذارم.\n\n"
        
        "📢 ویدیوهای معمولی و <b>Shorts</b> رو هم پوشش می‌دم.\n\n"
        
        "🔗 لینک ویدیو رو برات می‌ذارم و تا جای ممکن عکس "
        "بندانگشتی و اطلاعات ویدیو رو هم همراهش می‌فرستم.\n\n"
        
        "⏰ کانال یوتیوب رو مرتب بررسی می‌کنم تا ویدیوهای "
        "جدید رو سریع بهت برسونم.\n\n"
        
        "💛 خلاصه که من اینجام تا تو فقط بشینی و حال کنی؛ "
        "پیدا کردن و خبر دادن ویدیوهای جدید با من!\n\n"
        
        
        "دمت گرم که همراهمونی 🌱"
    )

    result = telegram(
        "sendMessage",
        {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
    )

    state["intro_posted"] = True
    state["intro_message_id"] = result.get("message_id")

    save_state(state)

    print(
        f"Intro published: message_id={result.get('message_id')}"
    )


if __name__ == "__main__":
    main()
