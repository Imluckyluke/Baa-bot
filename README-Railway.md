# 🐑 BaaBot — Railway Deployment Guide

## مراحل دیپلوی روی Railway

### ۱. ساخت پروژه در Railway
1. وارد [railway.app](https://railway.app) شوید
2. **New Project** → **Deploy from GitHub repo** را انتخاب کنید
3. ریپوی پروژه را انتخاب کنید

### ۲. اضافه کردن سرویس‌های Postgres و Redis
در داشبورد Railway:
- **New** → **Database** → **PostgreSQL** را اضافه کنید
- **New** → **Database** → **Redis** را اضافه کنید

Railway به‌طور خودکار متغیرهای زیر را تنظیم می‌کند:
- `DATABASE_URL`
- `REDIS_URL`
- `PORT`

### ۳. تنظیم متغیرهای محیطی
در بخش **Variables** سرویس بات، اضافه کنید:

| متغیر | مقدار |
|-------|-------|
| `BOT_TOKEN` | توکن بات تلگرام شما |
| `OPERATOR_IDS` | آیدی عددی ادمین‌ها (با کاما جدا کنید) |
| `WEBHOOK_HOST` | آدرس Railway شما: `https://YOUR_APP.up.railway.app` |
| `WEBHOOK_PATH` | `/webhook` |

### ۴. دریافت آدرس Railway
بعد از اولین دیپلوی:
- به تب **Settings** → **Networking** بروید
- **Generate Domain** را بزنید
- آدرس را در `WEBHOOK_HOST` وارد کنید

### ۵. دیپلوی
Railway خودکار `Dockerfile` را شناسایی و بیلد می‌کند.  
Migration دیتابیس نیز به‌طور خودکار قبل از اجرای بات انجام می‌شود.

---

## تغییرات اعمال‌شده برای Railway

| فایل | تغییر |
|------|-------|
| `bot/config.py` | پشتیبانی از `PORT` env var + تبدیل خودکار `postgres://` به `postgresql+asyncpg://` |
| `bot/main.py` | استفاده از `settings.PORT` به‌جای هاردکد `8080` |
| `Dockerfile` | تنظیم `ENV PORT=8080` به‌عنوان مقدار پیش‌فرض |
| `railway.toml` | تنظیمات بیلد و restart policy |
| `.env.example` | راهنمای متغیرهای Railway |

## حالت‌های اجرا

- **روی Railway**: حتماً `WEBHOOK_HOST` را تنظیم کنید (حالت Webhook)
- **محلی / توسعه**: `WEBHOOK_HOST` را خالی بگذارید (حالت Polling)
