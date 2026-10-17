# LikBy Provider Contract Testing

---

## 1. Storage Repository Contracts

All repository implementations (`SQLite`, `Supabase`, `Firestore`, `R2`) adhere to abstract interfaces defined in `src/likby/repositories/interfaces/`:
- `UserRepository`
- `ProfileRepository`
- `SubscriptionRepository`
- `MediaQuotaRepository`
- `SocialRepository`

Contract test fixtures verify that mock and concrete implementations behave identically under concurrent reads, writes, and constraint violations.
