# LikBy Security & Privacy Threat Model

**Platform:** LikBy  
**Last Updated:** 2026-10-19  

---

## 1. Threat Model & Assets

### 1.1 Protected Assets
1. **User Identity & Cryptographic Handles:** Public UUIDs and `likby_id` handles. Internal auto-increment IDs and private credentials are never exposed.
2. **Chat Transcripts & Private Messages:** Persisted until deliberate user deletion. Protected from cross-user access via strict participant checks.
3. **User Media Assets:** Photos, voice notes, and videos stored under partitioned SHA-256 content hashes (`media/{hash[:2]}/{hash[2:4]}/{hash}.{ext}`). Delivered only through time-limited signed URLs.
4. **Financial Transactions & Quotas:** Authoritative subscription entitlements, Razorpay payment orders, and daily usage ledgers.

---

## 2. Trust Boundaries & Enforcement

| Entry Point / Channel | Threat / Attack Vector | Mitigation & Enforcement Mechanism |
|---|---|---|
| **Telegram Webhook** | Spoofed updates, denial of service | Enforces `X-Telegram-Bot-Api-Secret-Token` header validation matching `settings.webhook_secret_token`. |
| **Telegram Mini App** | Client tampering, identity forgery, `initDataUnsafe` injection | Backend validates cryptographic HMAC-SHA256 signature using `bot_token`. Rejects any untrusted client data. |
| **Mini App Replay Attacks** | Leaked/captured query string replay | Enforces `auth_date` age check (`max_age_seconds: int = 86400`). Rejects signatures older than 24 hours or in the future. |
| **WebSocket Duels** | Unauthorized room joining, eavesdropping | Verifies caller identity and validates session membership against `play_game_participants`. Rejects intruders with WS 1008. |
| **Razorpay Payments** | Webhook replay, signature spoofing, fake payment verification | Validates HMAC-SHA256 signature against raw request bytes. Idempotent ledger `payment_transactions` prevents double crediting. |
| **Content Scraping & Piracy** | Forwarding private media, unauthorized downloading | All outbound Telegram media messages use `protect_content=True` to deter casual forwarding and saving. |

---

## 3. Privacy & Data Governance

1. **Zero-Advertising Tenet:** LikBy collects only data necessary for matchmaking, friendship management, and gaming. No user data is ever sold or provided to third-party ad networks.
2. **Non-Negotiable Persistence:** No self-destructing or ephemeral messages. Conversation history persists reliably until deliberate, authorized user deletion.
3. **Audit Logging:** Structural changes to user profiles (`display_name`, `bio`, `dob`, `gender`, `preferred_gender`, `location`, `relationship_intent`) trigger automated audit entries in `audit_events`.
4. **Secret Protection:** Secrets are loaded exclusively via environment variables and Pydantic `SecretStr`. Never committed to Git or printed in application logs.
