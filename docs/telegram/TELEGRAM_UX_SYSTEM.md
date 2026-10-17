# LikBy Telegram UX & Message Design System

---

## 1. Visual Hierarchy & Formatting Guidelines

- **Typography & Clean Lines:** Use clean Markdown formatting with clear section headers (`#`, `##`) and divider lines (`---`).
- **Restrained Emoji Palette:** Use purposeful emojis for navigation cues (e.g., 🔍 Discover, 🎮 Play, 👤 Profile, ⚙️ Settings). Avoid distracting decorative spam.
- **In-Place Message Editing:** When navigating menus or viewing profiles, edit the existing message rather than flooding the user's chat with new messages.
- **Keyboard Patterns:**
  - Standard bottom action bar: `[ 🔍 Find ] [ 🎮 Games ] [ 👤 Profile ]`
  - Inline navigation: `[ ⬅️ Back ] [ 🏠 Home ] [ 🔄 Refresh ]`

---

## 2. Respectful Tone for Quota Notices

When a user reaches a daily quota limit:
- State the exact limit reached clearly.
- Inform them of the next reset time (`00:00 UTC`).
- Provide alternative free actions (e.g., play solo games, chat with existing friends).
- Offer optional upgrade details without pressure or deceptive urgency.

*Example Message:*
> ℹ️ **Daily Discovery Limit Reached**  
> You have used your 3 daily profile searches for today. Your searches will refresh at **00:00 UTC**.  
> In the meantime, you can continue chatting with your friends or play our unlimited solo games!  
> *(Optional: Tap below to explore LIKBY Spark or Premium)*
