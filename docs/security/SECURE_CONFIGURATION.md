# LikBy Secure Configuration Guidelines

---

## 1. Environment Variable Hygiene

- Never commit real credentials to version control.
- Keep `.env.example` populated with dummy keys only.
- In production, set `APP_ENV=production` which enforces:
  - Strict HTTPS URLs for `PUBLIC_BASE_URL`.
  - Mandatory `TELEGRAM_WEBHOOK_SECRET` with minimum 32 characters entropy.
  - Fail-fast validation of required cloud secrets.
