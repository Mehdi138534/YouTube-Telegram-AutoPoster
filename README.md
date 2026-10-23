# Sir Mr Yellow Telegram AutoPoster

Posts new YouTube uploads (videos, Shorts) to a Telegram channel, and runs a small webhook bot with /start and /about.

## Files
- `bot.py`: checks the channel every 10 minutes (GitHub Actions) and posts anything new. State lives in `state.json`.
- `publish_intro.py`: posts the one-time intro message (manual workflow).
- `webhook.py`: Telegram bot webhook (Flask). Deploy on Render using `render.yaml`.
- `set_webhook.py`: registers the webhook URL with Telegram.

## Secrets (GitHub Actions)
`YOUTUBE_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## Render env vars
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, optional `YOUTUBE_URL`, `TELEGRAM_URL`.

## Register the webhook
Set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_URL` (your Render URL), `TELEGRAM_WEBHOOK_SECRET`, then run `python set_webhook.py`.
