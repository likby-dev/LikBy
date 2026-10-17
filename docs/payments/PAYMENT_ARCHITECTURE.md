# LikBy Unified Payment Architecture

---

## 1. Channel Separation & Policy Compliance

LikBy maintains two distinct payment adapters to ensure strict compliance with platform rules:

```
                  User Initiates Purchase
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   Inside Telegram Bot               Outside Telegram (Web)
            │                                 │
            ▼                                 ▼
    Telegram Stars (XTR)                 Razorpay (INR / Cards)
(Fully App Store Compliant)        (Web Subscriptions & Physical Goods)
```

1. **Telegram In-App Purchases:** All digital subscriptions and Spark passes sold inside Telegram use **Telegram Stars** (`currency="XTR"`), complying fully with Apple App Store and Google Play digital goods guidelines.
2. **Web / External Purchases:** Razorpay is maintained as a separate, isolated adapter for compliant out-of-Telegram transactions.
