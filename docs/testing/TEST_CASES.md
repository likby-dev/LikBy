# LikBy Automated Test Catalog & Cases

---

## 1. Unit Test Matrix (Summary of 116 Passed Tests)

| Test Module | Key Assertions Covered |
|:---|:---|
| `test_media_protection_and_quotas.py` | Tier quotas (Base 20/10, Spark 40/20, Premium 100/50, Diamond 250/100), `protect_content=True` on dispatches, file size rejection, atomic rollback on delivery failure, zero advertising & no self-destructing media assertions. |
| `test_play_games.py` | Registration of all 17 games, win conditions and mechanics for 11 Duel Games and 6 Solo Games. |
| `test_gaming_entitlements.py` | Base tier 5 duel plays/day limit and 6th rejection, unlimited solo games with 0 duel quota consumption, atomic dual-player reservation, Asia/Kolkata & UTC reset calculation. |
| `test_payment_verification.py` | Telegram Stars invoice checkout, pre-checkout validation, successful payment settlement, Razorpay HMAC-SHA256 signature verification, idempotent activation. |
| `test_referral_rewards.py` | Referral link generation, self-referral rejection, qualified referral granting 24h Spark pass, 30-day rolling cap of 3 Spark passes. |
| `test_scorer.py` | Compatibility scoring, gender/age filter validation, language overlap Jaccard similarity. |
| `test_social_service.py` | Mutual like transitions, friend capacity enforcement (Base max 3), unmatching, blocking. |
| `test_unique_id.py` | `likby_id` regex validation, immutability, uniqueness enforcement. |
| `test_user.py` | Initial state, age verification (18+), karma penalty, report thresholds, suspension. |
