# LikBy Quota & Resource Usage Policy

---

## 1. Daily Reset Rules

- **Reset Time:** All daily counters reset strictly at `00:00:00 UTC`.
- **Counting Definitions:**
  - **Upload:** One media item (photo, video, voice note, document) sent to an active chat.
  - **Receive:** One media item delivered to a recipient.
  - **Search:** One execution of profile discovery or handle lookup.
  - **Duel Play:** One initiated and accepted 2-player game session.
  - **Solo Play:** Casual single-player puzzle or challenge (unmetered on Base).

---

## 2. Two-Phase Reservation & Compensation Architecture

To prevent unfair quota loss due to transmission errors or delivery failures:
1. **Phase 1 (Reservation):** When Alice uploads a file for Bob, the system reserves 1 upload credit for Alice and 1 receive credit for Bob.
2. **Phase 2 (Commit or Rollback):**
   - If Telegram dispatches the message successfully, reservations are **committed**.
   - If dispatch fails (e.g. Bob blocked bot, Telegram network drop), reservations are **rolled back** immediately, ensuring no credits are lost.
