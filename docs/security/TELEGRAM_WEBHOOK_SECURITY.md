# LikBy Telegram Webhook Security Architecture

---

## 1. Authentication Flow

When configuring the Telegram webhook:
```bash
POST https://api.telegram.org/bot<TOKEN>/setWebhook
{
  "url": "https://api.likby.com/api/v1/telegram/webhook",
  "secret_token": "<HIGH_ENTROPY_TOKEN>",
  "allowed_updates": ["message", "callback_query", "pre_checkout_query"]
}
```

## 2. Inbound Validation
1. FastAPI middleware inspects the incoming request header `X-Telegram-Bot-Api-Secret-Token`.
2. Compares token against `TELEGRAM_WEBHOOK_SECRET` using `hmac.compare_digest` (constant-time comparison).
3. If token is invalid or missing, immediately returns `401 Unauthorized` without parsing the JSON body.
