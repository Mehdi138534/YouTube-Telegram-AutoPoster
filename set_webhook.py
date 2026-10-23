import os
import sys
import requests

token = os.environ.get("TELEGRAM_BOT_TOKEN")
webhook_url = os.environ.get("TELEGRAM_WEBHOOK_URL")
secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")

if not token or not webhook_url or not secret:
    print("Set TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_URL and TELEGRAM_WEBHOOK_SECRET first.")
    sys.exit(1)

webhook_url = webhook_url.rstrip("/") + "/telegram"

r = requests.post(
    f"https://api.telegram.org/bot{token}/setWebhook",
    json={
        "url": webhook_url,
        "secret_token": secret,
        "allowed_updates": ["message", "callback_query"],
    },
    timeout=30,
)
r.raise_for_status()
print(r.json())
