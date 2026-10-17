# Runbook: Failed Webhook Recovery

1. Check Render service logs for startup crashes or 502 Bad Gateway errors.
2. Confirm `PUBLIC_BASE_URL` is reachable via HTTPS.
3. Re-register webhook via `curl -F "url=https://api.likby.com/api/v1/telegram/webhook" -F "secret_token=..." https://api.telegram.org/bot<TOKEN>/setWebhook`.
