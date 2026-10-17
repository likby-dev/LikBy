# LikBy Media Security & Privacy Policy

---

## 1. Content Protection (`protect_content=True`)

All media relayed to chat partners is transmitted with `protect_content=True`:
- Blocks forwarding in Telegram.
- Prevents saving to device gallery.
- Inhibits screenshots on supported mobile operating systems.

## 2. Storage Hardening
- Media files are keyed by deterministic SHA-256 hashes (`media/{h[:2]}/{h[2:4]}/{h}.{ext}`).
- User-supplied filenames are never written to disk or S3/R2 keys.
- Uploaded MIME types and magic bytes are verified to prevent executable upload attacks.
