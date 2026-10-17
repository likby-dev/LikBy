# ADR-009: Telegram Stars Native In-App Payments & Razorpay Separation

- **Status:** Accepted & Implemented
- **Date:** 2026-10-15
- **Context:** Telegram and mobile app store policies require digital goods sold inside Telegram bots to use Telegram Stars (`currency="XTR"`). Standard card checkouts inside the bot violate these policies.
- **Decision:** Implement native Telegram Stars for in-bot subscriptions (`send_invoice`, `pre_checkout_query`, `successful_payment`). Isolate Razorpay strictly for compliant out-of-Telegram web payments.
- **Alternatives Considered:** Embedding Razorpay checkout links inside Telegram bot messages.
- **Consequences:** Complete App Store and Telegram policy compliance, zero risk of bot suspension.
