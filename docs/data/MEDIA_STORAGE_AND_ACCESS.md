# LikBy Media Storage & Archival Architecture

---

## 1. Dual Media Storage Strategy

LikBy employs a dual-path media architecture:
1. **Telegram-Native Relay (`file_id`):** For fast, cost-free, zero-egress delivery directly within Telegram chats. Dispatched with `protect_content=True`.
2. **Independent Cloudflare R2 Archival:** Background archival of original media to Cloudflare R2 bucket (`likby-media-prod`) ensuring that LikBy retains durable access even if Telegram file caches expire or are purged.

---

## 2. Deterministic Key Derivation

Media objects are hashed via SHA-256 to ensure de-duplication and prevent path traversal:
```
Key Format: media/{sha256[:2]}/{sha256[2:4]}/{sha256}.{extension}
Example:    media/4f/9a/4f9a12c8b...e901.jpg
```
User-supplied filenames are stripped and discarded.
