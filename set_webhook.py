import os
import sys
import requests

token = os.environ.get("TELEGRAM_BOT_TOKEN")
webhook_url = os.environ.get("TELEGRAM_WEBHOOK_URL")

if not token or not webhook_url:
    print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_URL first.")
    sys.exit(1)

r = requests.post(
    f"https://api.telegram.org/bot{token}/setWebhook",
    json={"url": webhook_url},
    timeout=30,
)
r.raise_for_status()
print(r.json())
