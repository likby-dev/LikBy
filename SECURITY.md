# Security Policy — LikBy

Security, privacy, and trust are foundational to **LikBy**. This document outlines our vulnerability disclosure policy, security controls, and reporting guidelines.

---

## 1. Supported Versions

| Version / Branch | Supported | Security Maintenance |
|:---|:---:|:---|
| `main` (Latest) | ✅ Yes | Active patch and dependency updates |
| Releases `< 1.0` | ❌ No | Please upgrade to latest `main` |

---

## 2. Reporting a Vulnerability

If you discover a security vulnerability within LikBy, please do **NOT** open a public GitHub issue.

Please report vulnerabilities privately:
- **Email:** `security@likby.com` (or contact project maintainers directly via authorized channels).
- **Include:**
  - Description of the vulnerability.
  - Step-by-step reproduction instructions or proof-of-concept script.
  - Potential impact assessment.
  - Affected components, endpoints, or file paths.

We will acknowledge receipt within **24 hours** and provide an initial response with a remediation timeline within **72 hours**.

---

## 3. Core Security Principles & Controls

### 3.1 Content Protection
- All media files relayed via Telegram are sent with `protect_content=True`.
- This prevents in-app forwarding, saving to camera roll, and basic screenshots on supported Telegram mobile clients.
- We maintain honest communication with users: no platform can mathematically prevent a photograph taken with an external physical camera.

### 3.2 Non-Negotiable Persistence & User Data Rights
- Chats and media do not use artificial self-destruction countdowns or disappearing media timers.
- Deletion is strictly user-initiated or triggered by compliance/administrative abuse resolution.
- Hard deletions purge media metadata and invoke background removal of underlying object storage assets.

### 3.3 Zero Advertising & Data Isolation
- LikBy does not integrate any ad network SDKs, tracking pixels, or third-party data brokers.
- User data is never sold or used for ad targeting.

### 3.4 Webhook & Callback Verification
- **Telegram Webhook:** Requires and verifies `X-Telegram-Bot-Api-Secret-Token`.
- **Telegram Mini App (`initData`):** Cryptographically validated using HMAC-SHA256 with the bot token. Unsafe client inputs (`initDataUnsafe`) are never trusted for identity or authorization.
- **Razorpay Webhooks:** Authenticated via HMAC-SHA256 signature verification over raw incoming payload bytes using the configured webhook secret.

### 3.5 Secrets Management & Zero-Leak Policy
- Secrets must never be committed to Git.
- Log sanitization middleware masks user tokens, payment credentials, and personally identifiable information (PII).
- Production deployments must supply credentials via secure environment variables (Render Secret Groups, Cloud Secret Managers).

### 3.6 Storage Security & Anti-Path-Traversal
- Uploaded media files are stored using deterministic, opaque SHA-256 content hashes (`media/{hash[:2]}/{hash[2:4]}/{hash}.{ext}`).
- User-supplied filenames and path parameters are never trusted or directly passed to filesystem APIs.
