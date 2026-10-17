# LikBy User Journeys

---

## Journey 1: New User Onboarding & First Match
1. **Entry:** User discovers bot via a referral link: `https://t.me/LikByBot?start=ref_alex99`.
2. **Welcome Screen:** Engaging welcome banner introducing LikBy core values (Safety, Privacy, Casual Gaming).
3. **Profile Creation:** Conversational FSM prompts for:
   - Display Name
   - Age verification (must be 18+)
   - Gender & Target preference
   - Primary languages & short bio
   - Public unique handle (`likby_id`)
4. **First Discovery:** User taps "🔍 Find People" and views nearby compatible profiles.
5. **Mutual Like:** User likes Bob; Bob reciprocates; immediate notification: "🎉 It's a Match! Say hello or invite to a game."

---

## Journey 2: Media Sharing with Content Protection
1. **Chat Session:** Alice and Bob are in an active conversation.
2. **Media Dispatch:** Alice sends a photograph.
3. **Server Validation:**
   - Alice's daily upload quota checked (e.g. 1/20 used).
   - Bob's daily receive quota checked (e.g. 0/10 used).
   - File size verified (under 10MB tier cap).
4. **Relay:** Message delivered to Bob with `protect_content=True`. Bob cannot forward, save to camera roll, or take native screenshots in supported Telegram clients.
5. **Receipt:** Quota reservations commit atomically.

---

## Journey 3: Challenging a Friend to a Duel Game
1. **Initiation:** User taps "🎮 Play Games" -> "⚔️ Duel Games" -> Selects "Air Rush".
2. **Challenge Sent:** Opponent receives an interactive challenge card with "Accept" / "Decline" buttons.
3. **Gameplay:** Upon acceptance, the Mini App opens or interactive inline keyboard updates in real time.
4. **Conclusion:** Server validates the win condition, awards social karma points, and records game history.
