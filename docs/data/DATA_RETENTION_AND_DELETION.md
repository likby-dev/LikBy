# LikBy Data Retention & Deletion Policy

---

## 1. Retention Standards

- **Active Conversations & Media:** Retained indefinitely under the non-negotiable persistence rule until explicit user deletion.
- **Quota Event Logs (`media_quota_events`):** Retained for 90 days for audit and rate-limit reconciliation; archived thereafter.
- **Payment & Stars Transaction Records:** Retained for 7 years to comply with tax and statutory accounting regulations.

---

## 2. Right to Erasure (User-Initiated Deletion)

When a user triggers `/privacy` -> "Delete Account":
1. Immediate revocation of profile visibility and active chat session tokens.
2. Soft-delete flag set for 7 days (grace period allowing accidental cancellation).
3. Hard-delete worker scrubs user row, profile data, and initiates R2 object removal after 7 days.
