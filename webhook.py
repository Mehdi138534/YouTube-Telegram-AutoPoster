"""Telegram webhook for the private /start and /about menu."""
import hmac
import logging
import os

import requests
from flask import Flask, jsonify, request

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("telegram-webhook")
app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
YOUTUBE_URL = os.getenv("YOUTUBE_URL", "https://www.youtube.com/@Sir_Mr_yellow138")
TELEGRAM_URL = os.getenv("TELEGRAM_URL", "https://t.me/Sirmryellow138")

START_TEXT = (
    "🤖 <b>من کی‌ام؟</b>\n\nسلام رفیق! 👋💛\n"
    "من باتِ <b>Sir Mr Yellow</b> ـم؛ یه رفیق خودمونی که حواسش به ویدیوهای تازه‌ی کاناله 😎\n\n"
    "🎬 هر وقت ویدیوی عمومی تازه‌ای منتشر بشه، خبر و لینک تماشاش رو توی کانال تلگرام می‌ذارم.\n"
    "📱 ویدیوهای معمولی و شورت‌ها رو پوشش می‌دم؛ تشخیص شورت تقریبیه چون API رسمی یوتیوب برچسب قطعی نداره.\n\n"
    "💛 تو فقط نوتیفیکیشن کانال رو روشن کن و حال کن؛ خبررسانی با من! دمت گرم که همراهمونی 🌱"
)
ABOUT_TEXT = (
    "🤖 <b>درباره بات Sir Mr Yellow</b>\n\nسلام رفیق! 👋\n"
    "من ویدیوهای عمومی تازه‌ی کانال یوتیوب Sir Mr Yellow رو بررسی می‌کنم و لینک‌شون رو با یه پیام صمیمی توی تلگرام می‌ذارم.\n\n"
    "برای دیدن آخرین پست‌ها، کانال تلگرام رو دنبال کن 💛"
)


def tg_call(method, payload):
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    response = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", json=payload, timeout=15)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method}: {data.get('description', 'unknown error')}")
    return data.get("result")


def menu():
    return {"inline_keyboard": [
        [{"text": "🤖 درباره بات", "callback_data": "about"}],
        [{"text": "🎬 کانال یوتیوب", "url": YOUTUBE_URL}, {"text": "📢 کانال تلگرام", "url": TELEGRAM_URL}],
    ]}


def back_menu():
    return {"inline_keyboard": [
        [{"text": "💛 برگشت به منوی اصلی", "callback_data": "home"}],
        [{"text": "🎬 یوتیوب", "url": YOUTUBE_URL}, {"text": "📢 تلگرام", "url": TELEGRAM_URL}],
    ]}


@app.get("/")
def index():
    return "Sir Mr Yellow bot is online."


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/telegram")
def webhook():
    if not SECRET or not hmac.compare_digest(request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), SECRET):
        return ("Forbidden", 403)
    update = request.get_json(silent=True) or {}
    try:
        callback = update.get("callback_query") or {}
        if callback:
            callback_id = callback.get("id")
            if callback_id:
                tg_call("answerCallbackQuery", {"callback_query_id": callback_id})
            message = callback.get("message") or {}
            chat = message.get("chat") or {}
            if chat.get("type") == "private" and message.get("message_id"):
                data = callback.get("data")
                if data in ("about", "home"):
                    tg_call("editMessageText", {
                        "chat_id": chat["id"], "message_id": message["message_id"],
                        "text": ABOUT_TEXT if data == "about" else START_TEXT,
                        "parse_mode": "HTML", "disable_web_page_preview": True,
                        "reply_markup": back_menu() if data == "about" else menu(),
                    })
            return ("OK", 200)

        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        if chat.get("type") == "private" and text.startswith("/"):
            command = text.split()[0].split("@", 1)[0].lower()
            if command in ("/start", "/about"):
                tg_call("sendMessage", {
                    "chat_id": chat["id"], "text": START_TEXT if command == "/start" else ABOUT_TEXT,
                    "parse_mode": "HTML", "disable_web_page_preview": True,
                    "reply_markup": menu() if command == "/start" else back_menu(),
                })
    except Exception:
        # Acknowledge valid updates even if Telegram's API is temporarily failing, to avoid
        # endless webhook redelivery and duplicate replies. Details stay in server logs.
        log.exception("Could not process Telegram update %s", update.get("update_id", "unknown"))
    return ("OK", 200)


if __name__ == "__main__":
    raise SystemExit("Run with gunicorn, not Flask's development server")
