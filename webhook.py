import os

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SECRET = os.environ["TELEGRAM_WEBHOOK_SECRET"]
YOUTUBE_URL = os.getenv("YOUTUBE_URL", "https://www.youtube.com/@Sir_Mr_yellow138")
TELEGRAM_URL = os.getenv("TELEGRAM_URL", "https://t.me/Sirmryellow138")
TG_BASE = f"https://api.telegram.org/bot{TOKEN}"


START_TEXT = (
    "🤖 <b>من کی‌ام؟</b>\n\n"
    "سلام رفیق! 👋💛\n"
    "من باتِ <b>Sir Mr Yellow</b> ـم؛ اومدم که نذارم هیچ ویدیوی جدیدی از رفیقت از دستت در بره! 😎🔥\n\n"
    "کار من خیلی ساده‌ست:\n\n"
    "🎬 هر وقت توی کانال یوتیوب <b>Sir Mr Yellow</b> یه ویدیوی جدید منتشر بشه، من می‌رم سراغش و خبرشو توی کانال تلگرام می‌ذارم.\n\n"
    "📢 ویدیوهای معمولی و <b>Shorts</b> رو هم پوشش می‌دم.\n\n"
    "🔗 لینک ویدیو رو برات می‌ذارم و تا جای ممکن عکس بندانگشتی و اطلاعات ویدیو رو هم همراهش می‌فرستم.\n\n"
    "⏰ کانال یوتیوب رو مرتب بررسی می‌کنم تا ویدیوهای جدید رو سریع بهت برسونم.\n\n"
    "💛 خلاصه که من اینجام تا تو فقط بشینی و حال کنی؛ پیدا کردن و خبر دادن ویدیوهای جدید با من!\n\n"
    "اگه رفیق <b>Sir Mr Yellow</b> هستی، خوش اومدی داداش! 😎💛\n"
    "دمت گرم که همراهمونی 🌱"
)

ABOUT_TEXT = (
    "🤖 <b>درباره بات Sir Mr Yellow</b>\n\n"
    "سلام رفیق! 👋💛\n"
    "من باتِ Sir Mr Yellow ـم؛ یه رفیق کوچیک که اومده نذاره هیچ ویدیوی جدیدی از کانالمون از دستت در بره! 😎🔥\n\n"
    "<b>کار من چیه؟</b>\n"
    "🎬 هر وقت ویدیوی جدیدی روی یوتیوب منتشر بشه، من خبرش رو توی کانال تلگرام می‌رسونم.\n"
    "📱 ویدیوهای معمولی و Shorts رو هم پوشش می‌دیم.\n"
    "🖼️ تا جای ممکن عکس بندانگشتی و لینک مستقیم ویدیو هم همراه پست میاد.\n"
    "⏰ کانال یوتیوب مرتب بررسی می‌شه تا ویدیوهای تازه رو سریع به دستت برسونیم.\n\n"
    "خلاصه رفیق، تو فقط بشین و حال کن؛\n"
    "پیدا کردن و خبر دادن ویدیوهای جدید با من! 😎🤝\n\n"
    "💛 مرام ما اینه که نذاریم از جمع جا بمونی.\n"
    "دمت گرم که کنارمونی! 🌱"
)


def telegram(method, payload):
    r = requests.post(f"{TG_BASE}/{method}", json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data)
    return data["result"]


def main_menu():
    return {
        "inline_keyboard": [
            [
                {"text": "🤖 درباره بات", "callback_data": "about_bot"},
            ],
            [
                {"text": "🎬 کانال یوتیوب", "url": YOUTUBE_URL},
                {"text": "📢 کانال تلگرام", "url": TELEGRAM_URL},
            ],
        ]
    }


def back_menu():
    return {
        "inline_keyboard": [
            [{"text": "💛 برگشت به منوی اصلی", "callback_data": "main_menu"}],
            [
                {"text": "🎬 یوتیوب", "url": YOUTUBE_URL},
                {"text": "📢 تلگرام", "url": TELEGRAM_URL},
            ],
        ]
    }


@app.get("/")
def index():
    return "Sir Mr Yellow bot is online."


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/telegram")
def webhook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != SECRET:
        return ("Not found", 404)

    update = request.get_json(silent=True) or {}

    # Inline-button interactions.
    callback = update.get("callback_query") or {}
    if callback:
        callback_id = callback.get("id")
        data = callback.get("data")
        message = callback.get("message") or {}
        chat = message.get("chat") or {}

        if callback_id:
            telegram("answerCallbackQuery", {"callback_query_id": callback_id})

        if chat.get("type") == "private":
            if data == "about_bot":
                telegram("editMessageText", {
                    "chat_id": chat["id"],
                    "message_id": message["message_id"],
                    "text": ABOUT_TEXT,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                    "reply_markup": back_menu(),
                })
            elif data == "main_menu":
                telegram("editMessageText", {
                    "chat_id": chat["id"],
                    "message_id": message["message_id"],
                    "text": START_TEXT,
                    "reply_markup": main_menu(),
                    "disable_web_page_preview": True,
                })

        return ("OK", 200)

    # Normal messages / commands.
    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}

    if chat.get("type") == "private":
        command = text.split("@", 1)[0].lower()

        if command in {"/start", "/about"}:
            telegram("sendMessage", {
                "chat_id": chat["id"],
                "text": START_TEXT if command == "/start" else ABOUT_TEXT,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": back_menu() if command == "/about" else main_menu(),
            })

    return ("OK", 200)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
