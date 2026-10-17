# LikBy Render Deployment Guide

---

## 1. Blueprint Configuration (`render.yaml`)

LikBy includes a pre-configured Render Blueprint (`render.yaml`) defining a Web Service running on Python:
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn likby.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path:** `/health/live`

---

## 2. Production Cautions (Render Free Tier)

- **Ephemeral Storage:** The local filesystem is wiped upon service restart or deployment. For production, set `STORAGE_BACKEND=supabase` and `MEDIA_STORAGE_BACKEND=cloudflare_r2`.
- **Spin-down:** Free services spin down after 15 minutes of inactivity. For production Telegram webhooks, upgrade to Render Starter ($7/month) to prevent 30-50s cold start latency.
