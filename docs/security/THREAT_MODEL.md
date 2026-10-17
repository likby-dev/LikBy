# LikBy Security Threat Model (STRIDE)

**Methodology:** Microsoft STRIDE Threat Modeling Framework  
**Scope:** Telegram Bot API, FastAPI Gateway, Database Adapters, Media Storage

---

## 1. STRIDE Analysis Matrix

| Threat Category | Threat Description | Architectural Mitigation | Status |
|:---|:---|:---|:---:|
| **Spoofing** | Forged webhook requests claiming to be from Telegram | Secret token header verification (`X-Telegram-Bot-Api-Secret-Token`) | ✅ Verified |
| **Spoofing** | Forged Mini App user identities | Server-side HMAC-SHA256 validation of raw `initData` query string | ✅ Verified |
| **Tampering** | Modifying payment callback payload or amount | Razorpay HMAC-SHA256 signature verification over raw bytes | ✅ Verified |
| **Tampering** | Manipulating game board state from client | Server-authoritative game engine (`src/likby/games/`) | ✅ Verified |
| **Repudiation** | Denying an abusive message or media upload | Immutable audit logs and media quota event ledgers | ✅ Verified |
| **Information Disclosure** | Leaking private photos via URL guessing or forwards | Content protection (`protect_content=True`) + opaque SHA-256 keys | ✅ Verified |
| **Denial of Service** | Flooding media uploads or people searches | Strict server-enforced daily quotas and per-user rate limiters | ✅ Verified |
| **Elevation of Privilege** | Normal user calling admin / paid tier actions | Server-side subscription entitlement verification | ✅ Verified |
