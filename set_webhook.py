"""Register the Telegram webhook URL and secret token."""
import os
import sys
import requests


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    base_url = os.getenv("TELEGRAM_WEBHOOK_URL", "").strip().rstrip("/")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not token or not base_url or not secret:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_URL and TELEGRAM_WEBHOOK_SECRET first.")
    url = base_url if base_url.endswith("/telegram") else base_url + "/telegram"
    response = requests.post(f"https://api.telegram.org/bot{token}/setWebhook", json={
        "url": url, "secret_token": secret, "allowed_updates": ["message", "callback_query"]
    }, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise SystemExit(f"Telegram setWebhook failed: {data.get('description', data)}")
    print(f"Webhook registered: {url}")


if __name__ == "__main__":
    main()
