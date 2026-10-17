# LikBy Environment Configuration Reference

| Variable | Required In | Default / Description |
|:---|:---:|:---|
| `APP_ENV` | All | `development` or `production` |
| `STORAGE_BACKEND` | All | `local` (SQLite) or `supabase` (PostgreSQL) |
| `MEDIA_STORAGE_BACKEND` | All | `local` (filesystem) or `cloudflare_r2` |
| `TELEGRAM_MODE` | All | `polling` (local dev) or `webhook` (production) |
| `TELEGRAM_BOT_TOKEN` | All | Bot token from `@BotFather` |
| `TELEGRAM_WEBHOOK_SECRET` | Production | High-entropy secret for `X-Telegram-Bot-Api-Secret-Token` |
| `PUBLIC_BASE_URL` | Production | Public HTTPS base URL (e.g. `https://api.likby.com`) |
| `DATABASE_URL` | All | Async connection string (e.g. `sqlite+aiosqlite:///likby.db`) |
| `SUPABASE_URL` | Production | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Production | Supabase backend service-role key |
| `FIREBASE_CREDENTIALS_JSON` | Production | Service account JSON string for Firestore |
| `CLOUDFLARE_R2_ACCOUNT_ID` | Production | Cloudflare Account ID |
| `CLOUDFLARE_R2_ACCESS_KEY_ID` | Production | R2 Access Key |
| `CLOUDFLARE_R2_SECRET_ACCESS_KEY` | Production | R2 Secret Key |
| `CLOUDFLARE_R2_BUCKET` | Production | Bucket name (e.g. `likby-media-prod`) |
