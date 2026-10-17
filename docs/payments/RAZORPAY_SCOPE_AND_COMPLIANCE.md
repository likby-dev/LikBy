# LikBy Razorpay Scope, Security & Compliance

---

## 1. Compliance Boundaries
- **Rule:** Never serve Razorpay payment links inside the Telegram bot for digital goods (violates Telegram terms and mobile app store rules).
- **Scope:** Reserved exclusively for external public web payments or future physical merchandise sales.

---

## 2. Webhook Security Verification
All incoming webhooks at `/api/v1/payments/razorpay/webhook` require:
1. Retrieval of raw HTTP request body bytes.
2. Extraction of header `X-Razorpay-Signature`.
3. Computation of HMAC-SHA256 signature using `RAZORPAY_WEBHOOK_SECRET`.
4. Constant-time comparison via `hmac.compare_digest`.
