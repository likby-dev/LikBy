# LikBy Payment Security & Fraud Prevention

---

## 1. Telegram Stars Verification
- Digital subscriptions inside Telegram use native Stars (`currency="XTR"`).
- Entitlements are activated **only** upon receiving and verifying the `successful_payment` event from Telegram.
- Invoice creation or checkout display does **not** grant any quota or subscription state.

## 2. Razorpay Webhook Authentication
- Webhook signature is validated using HMAC-SHA256:
  ```python
  expected_sig = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
  is_valid = hmac.compare_digest(expected_sig, signature_header)
  ```
- Payment events are deduplicated by `payment_id` to prevent replay attacks.
