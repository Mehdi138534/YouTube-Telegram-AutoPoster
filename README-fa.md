# 🤖 Sir Mr Yellow — YouTube → Telegram Autoposter

بات تلگرامی پروژه **Sir Mr Yellow** برای انتشار خودکار ویدیوهای جدید یوتیوب در کانال تلگرام.

## قابلیت‌ها

- بررسی کانال YouTube هر ۱۰ دقیقه با GitHub Actions.
- انتشار ویدیوهای معمولی و Shorts.
- جلوگیری از ارسال تکراری با `state.json`.
- ارسال thumbnail در صورت در دسترس بودن؛ در صورت خطا، پیام متنی ارسال می‌شود.
- کپشن فارسی، صمیمی و خودمانی.
- انتشار پیام معرفی کانال از طریق Workflow جداگانه و فقط یک‌بار.
- پاسخ به `/start` در چت خصوصی با یک سرویس webhook جداگانه.
- توکن‌ها فقط از GitHub Secrets / Environment Variables خوانده می‌شوند.

> نکته: YouTube Data API یک فیلد قطعی برای «Shorts بودن» در این مسیر عمومی ارائه نمی‌کند. بات همه ویدیوها را منتشر می‌کند؛ برای برچسب «شورت» در این نسخه فقط وجود `#shorts` در عنوان ملاک است تا ویدیوهای عادی کوتاه اشتباهاً Shorts نامیده نشوند.

## ساختار

```text
bot.py
publish_intro.py
webhook.py
render.yaml
state.json
requirements.txt
.github/workflows/
  youtube-to-telegram.yml
  publish-intro.yml
```

## 1) Secrets

در GitHub → Settings → Secrets and variables → Actions این موارد را بساز:

| Secret | مقدار |
|---|---|
| `YOUTUBE_API_KEY` | کلید YouTube Data API |
| `TELEGRAM_BOT_TOKEN` | توکن BotFather |
| `TELEGRAM_CHAT_ID` | `@Sirmryellow138` |

بات باید در کانال تلگرام ادمین باشد و اجازه ارسال پیام و عکس داشته باشد.

## 2) انتشار خودکار ویدیو

Workflow **YouTube to Telegram** هر ۱۰ دقیقه اجرا می‌شود. زمان‌بندی GitHub ممکن است گاهی با تأخیر اجرا شود.

در اجرای اول:
- `INITIAL_POST_LIMIT=3` یعنی حداکثر ۳ ویدیوی موجود منتشر می‌شود.
- موارد قدیمی‌تر به‌عنوان دیده‌شده ثبت می‌شوند تا کانال با پست‌های قدیمی پر نشود.
- اگر می‌خواهی هیچ ویدیوی قدیمی در اجرای اول منتشر نشود، مقدار را به `0` تغییر بده.

پس از هر ارسال، شناسه ویدیو در `state.json` ذخیره می‌شود.

## 3) پیام معرفی کانال

Workflow **Publish Telegram Intro** را فقط از Actions → Run workflow اجرا کن.

این Workflow قبل از انتشار، `state.json` را بررسی می‌کند. بنابراین اجرای دوباره، پیام معرفی را تکرار نمی‌کند.

اگر عمداً خواستی دوباره منتشر شود، هنگام اجرای دستی گزینه `force` را فعال کن.

## 4) `/start` در چت خصوصی

GitHub Actions زمان‌بندی‌شده دائماً روشن نیست و نمی‌تواند به‌تنهایی منتظر `/start` بماند. برای `/start` یک سرویس webhook لازم است.

این پروژه `webhook.py` را برای این کار دارد.

### استقرار نمونه با Render

1. مخزن GitHub را به Render متصل کن.
2. یک **Web Service** بساز یا `render.yaml` را استفاده کن.
3. متغیرهای زیر را تنظیم کن:

| Variable | مقدار |
|---|---|
| `TELEGRAM_BOT_TOKEN` | همان توکن BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | یک رشته تصادفی طولانی که خودت انتخاب می‌کنی |
| `YOUTUBE_URL` | `https://www.youtube.com/@Sir_Mr_yellow138` |
| `TELEGRAM_URL` | `https://t.me/Sirmryellow138` |

Render برای سرویس یک آدرس HTTPS می‌دهد.

بعد باید webhook تلگرام را روی این مسیر تنظیم کنی. اسکریپت `set_webhook.py` خودش `/telegram` را به آدرس اضافه می‌کند و Secret را به‌صورت امن در Header استاندارد Telegram ثبت می‌کند:

```text
https://YOUR-RENDER-DOMAIN/telegram
```

بعد از تنظیم، Telegram آپدیت‌های بات را به این آدرس POST می‌کند و `/start` پاسخ می‌گیرد.

برای ثبت webhook می‌توانی روی کامپیوتر خودت این متغیرها را تنظیم کنی و `set_webhook.py` را اجرا کنی:

```text
TELEGRAM_BOT_TOKEN=توکن-بات
TELEGRAM_WEBHOOK_URL=https://YOUR-RENDER-DOMAIN/telegram
```

این کار توکن را داخل GitHub یا کد ذخیره نمی‌کند.

### نکته مهم درباره رایگان بودن

Free Web Service در Render ممکن است بعد از ۱۵ دقیقه بدون ترافیک متوقف شود و درخواست بعدی باعث راه‌اندازی دوباره آن شود؛ بنابراین برای `/start` روی پلن رایگان، «فوری و همیشه‌آنلاین» بودن تضمین نمی‌شود.

برای پروژه شخصی و آزمایشی مناسب است؛ برای پاسخ‌دهی کاملاً پایدار باید بعداً یک سرویس همیشه‌روشن استفاده شود.

## 5) مجوز GitHub Actions

در:

**Settings → Actions → General → Workflow permissions**

گزینه:

**Read and write permissions**

را فعال کن.

این پروژه برای ذخیره `state.json` به اجازه نوشتن نیاز دارد.

## 6) اجرای تست

اول Workflow اصلی را دستی اجرا کن.

اگر موفق بود، باید در لاگ چیزی شبیه این ببینی:

```text
Done. Published 1 new video(s).
```

بعد Workflow معرفی را جداگانه اجرا کن.

در نهایت، سرویس webhook را بالا بیاور، webhook تلگرام را تنظیم کن و در چت خصوصی بات `/start` بفرست.

## امنیت

- توکن بات را داخل کد نگذار.
- API Key یوتیوب را داخل فایل عمومی نگذار.
- `TELEGRAM_WEBHOOK_SECRET` را عمومی نکن.
- اگر توکن بات لو رفت، از BotFather آن را تعویض کن.

## بخش معرفی بات در چت خصوصی

بات در چت خصوصی یک منوی دوستانه دارد:

- `🤖 درباره بات` — معرفی کامل و خودمانی بات و کاری که انجام می‌دهد.
- `🎬 کانال یوتیوب` — لینک مستقیم کانال YouTube.
- `📢 کانال تلگرام` — لینک مستقیم کانال Telegram.
- `/about` — نمایش مستقیم بخش معرفی بات.
- `💛 برگشت به منوی اصلی` — بازگشت از معرفی به منوی اصلی بدون ارسال پیام جدید.

این منو از طریق webhook کار می‌کند؛ بنابراین اجرای Workflow زمان‌بندی‌شده GitHub Actions به‌تنهایی برای دریافت فوری `/start` کافی نیست. برای این قسمت باید `webhook.py` روی یک سرویس Web Service اجرا شود و webhook تلگرام به آن متصل باشد.
