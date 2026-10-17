# LikBy Architectural Glossary

- **Authoritative Tier:** One of four valid subscription plans (`base`, `spark`, `premium`, `diamond`) controlling server-side quotas.
- **Content Protection:** Telegram's native `protect_content=True` flag prohibiting message forwarding and saving.
- **Duel Game:** A 2-player turn-based or competitive match (11 total) consuming Base tier daily duel allowance (max 5/day).
- **Solo Game:** A single-player casual puzzle or arcade game (6 total) with unlimited plays for Base tier.
- **Friend Capacity:** The maximum number of mutual friendships a user can maintain (Base: 3, Spark: 5, Premium: 15, Diamond: 50).
- **`likby_id`:** The immutable or user-configured public alphanumeric handle (e.g., `@alex_99`) used for safe discovery without revealing phone numbers or database IDs.
- **Media Quota Event:** An immutable audit record of a media upload or receive action used to calculate daily quota consumption.
- **Non-Negotiable Persistence:** The architectural rule that chats and user media must never automatically disappear or self-destruct.
- **Spark Pass:** A 24-hour temporary premium pass granting Spark tier benefits, earned through referrals or purchased.
- **Telegram Mini App (TMA):** An HTML5/Canvas client running inside Telegram using `initData` authentication for rich gaming experiences.
- **Zero-Advertising Policy:** The strict platform commitment that no commercial advertising or sponsored content is served.
