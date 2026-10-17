# Telegram Bot API Feature Evaluation & Research

**Date Verified:** 2026-10-17  
**Official Sources:**  
- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)  
- [Telegram Mini Apps](https://core.telegram.org/bots/webapps)  
- [Telegram Digital Goods & Stars](https://core.telegram.org/bots/payments-stars)  
- [Telegram Features for Bots](https://core.telegram.org/bots/features)

---

## 1. Feature Evaluation Matrix

| Feature | User Benefit | Technical Requirements | Limitations | Security & Privacy Impact | Decision |
|:---|:---|:---|:---|:---|:---:|
| **Commands & Command Menu** | Discoverability of core actions (`/start`, `/profile`, `/play`, `/paysupport`) | `setMyCommands` API call at startup | Max 100 commands per scope | Public visibility; no sensitive args | **Implement now** |
| **Inline Keyboards & Callbacks** | Smooth, one-tap navigation without text typing | `aiogram.types.InlineKeyboardMarkup` | Callback data limited to 64 bytes | State injection risk if data unvalidated | **Implement now** |
| **Message Editing** | In-place view updates without chat spam | `edit_message_text`, `edit_message_reply_markup` | Cannot edit messages older than 48h | Prevents screen clutter & flickering | **Implement now** |
| **Deep Links & Start Parameters** | Frictionless onboarding & referral attribution | `/start <referral_code>` parsing | Parameter max 64 chars (a-zA-Z0-9_-) | Must validate against self-referral | **Implement now** |
| **Telegram Mini Apps (WebApps)** | Rich interactive canvas games & visual boards | HTTPS web app, `initData` validation | Requires web browser rendering engine | Must validate `initData` HMAC server-side | **Implement now** |
| **Content Protection (`protect_content`)** | Prevents forwarding, saving, and basic screenshots | Set `protect_content=True` on all media calls | Client-dependent; no defense against external camera | High user privacy benefit | **Implement now** |
| **Telegram Stars (`send_invoice`)** | Native in-app digital purchases for subscriptions | `send_invoice` with `currency="XTR"` | 21-day holding period for payouts | Fully compliant with App Store / Play Store | **Implement now** |
| **Chat Actions (Typing / Upload)** | Responsiveness feedback during processing | `send_chat_action("typing" / "upload_photo")` | Rate-limited by Telegram | User feels app is active | **Implement now** |
| **Inline Mode** | Sharing profiles or game invites in other chats | `InlineQueryHandler` in aiogram | Requires enabling inline mode in BotFather | Potential enumeration risk if unauthenticated | **Implement later** |
| **Built-in Polls & Quizzes** | Casual community questions | `send_poll` API | Fixed poll options; less flexible than custom game | Minimal security risk | **Optional** |
| **Ephemeral / Self-Destruct Messages** | Vanishing messages | Not supported via standard Bot API without deletion loops | Artificial countdowns cause data loss | **Violates LikBy non-negotiable persistence policy** | **Not appropriate** |
| **Third-Party Banner Ads** | Monetization | Ad network SDKs | Degrades premium feel; privacy risk | **Violates LikBy zero-advertising policy** | **Not appropriate** |

---

## 2. Research Conclusions & Architectural Impact

1. **Non-Negotiable Persistence:** The Telegram Bot API does not provide a native self-destruct mechanism for bots without destructive `deleteMessage` loops. LikBy explicitly rejects ephemeral disappearing messages. All chat history and media remain available to conversation participants until deliberate user deletion.
2. **Content Protection (`protect_content=True`):** Validated that `protect_content=True` on `send_photo`, `send_video`, `send_document`, `send_voice`, and `send_sticker` successfully instructs modern Telegram clients (iOS, Android, Desktop) to block message forwarding, export, and native screenshots.
3. **Telegram Stars Compliance:** Digital subscriptions sold inside Telegram must use Telegram Stars (`currency="XTR"`). Standard card checkout (e.g. Razorpay) inside the bot for digital goods violates Apple App Store and Google Play policies. Razorpay is maintained strictly for compliant out-of-Telegram web payments.
