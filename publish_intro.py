"""Publish the channel intro once (manual GitHub Actions workflow)."""
import json
import os
from pathlib import Path
import requests
from bot import load_state, save_state

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
YOUTUBE_URL = os.getenv("YOUTUBE_URL", "https://www.youtube.com/@Sir_Mr_yellow138")
TELEGRAM_URL = os.getenv("TELEGRAM_URL", "https://t.me/Sirmryellow138")

TEXT = (
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

KEYBOARD = {"inline_keyboard": [[{"text": "🎬 کانال یوتیوب Sir Mr Yellow", "url": YOUTUBE_URL}],
                                  [{"text": "📢 کانال تلگرام", "url": TELEGRAM_URL}]]}


def main():
    state = load_state()
    force = os.getenv("FORCE_INTRO", "0").lower() in ("1", "true", "yes")
    if state.get("intro_posted") and not force:
        print("Intro already posted; nothing to do.")
        return
    response = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": TEXT, "parse_mode": "HTML", "disable_web_page_preview": True, "reply_markup": KEYBOARD}, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram sendMessage failed: {data.get('description', data)}")
    result = data.get("result") or {}
    state["intro_posted"] = True
    state["intro_message_id"] = result.get("message_id")
    save_state(state)
    print(f"Intro published: message_id={result.get('message_id')}")


if __name__ == "__main__":
    main()
