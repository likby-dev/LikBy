# LikBy Automated Security Testing Suite

---

## 1. Attack Vectors Tested

1. **Webhook Forgery:** Inbound webhook payloads without valid `X-Telegram-Bot-Api-Secret-Token` are rejected with `401 Unauthorized`.
2. **Payment Callback Tampering:** Inbound Razorpay webhooks with forged or missing signatures are rejected with `400 Bad Request`.
3. **Replay Attacks:** Payment transaction IDs and referral codes cannot be redeemed multiple times.
4. **Quota Bypass:** Users cannot exceed daily media or discovery limits by sending concurrent parallel requests.
5. **Path Traversal Prevention:** Media keys derived from SHA-256 hashes prevent directory traversal attacks.
