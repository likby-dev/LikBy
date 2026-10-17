# Platform Limits, Quotas & Pricing Breakdown

**Date Verified:** 2026-10-17  
**Official Sources:**  
- Render Pricing: [https://render.com/docs/free](https://render.com/docs/free)  
- Supabase Pricing: [https://supabase.com/pricing](https://supabase.com/pricing)  
- Firebase Pricing: [https://firebase.google.com/docs/firestore/pricing](https://firebase.google.com/docs/firestore/pricing)  
- Cloudflare R2 Pricing: [https://developers.cloudflare.com/r2/pricing/](https://developers.cloudflare.com/r2/pricing/)  
- Telegram Bot API FAQ: [https://core.telegram.org/bots/faq](https://core.telegram.org/bots/faq)

---

## 1. Telegram Bot API Limits

| Resource / Action | Verified Limit | Architectural Safeguard |
|:---|:---|:---|
| **Max Payload Size (Webhook)** | 10 MB per update payload | Payload parser validates headers before reading stream |
| **File Upload (Bot API)** | 50 MB (send), 20 MB (download) | Tier size caps (Base: 10MB, Spark: 25MB, Premium: 50MB, Diamond: 100MB via MTProto/Cloudflare) |
| **Outbound Messages to Same User**| ~1 message per second | Per-user rate-limiting queue in dispatch worker |
| **Global Outbound Messages** | 30 messages per second across all chats | Global token bucket throttler in `chat_relay_service.py` |
| **Callback Data Length** | 64 bytes | State tokens and short action codes (`act:arg`) used |

---

## 2. Cloud Infrastructure Free-Tier & Pricing Comparison

### 2.1 Render
- **Free Tier:** 750 free instance hours/month, 512 MB RAM, spins down after 15 minutes of inactivity. Ephemeral local disk (wiped on restart/redeploy).
- **Production Recommendation:** Starter Service ($7/month) providing 512 MB RAM, zero spin-down, and persistent disk support.

### 2.2 Supabase PostgreSQL
- **Free Tier:** 500 MB database storage, 2 active projects, 50,000 monthly active users, 5 GB bandwidth. Inactivity pause after 7 days without queries.
- **Production Recommendation:** Supabase Pro ($25/month) eliminates pausing, adds daily automated backups, 8 GB database storage, and 250 GB bandwidth.

### 2.3 Firebase Cloud Firestore
- **Free Tier (Spark Plan):** 50,000 document reads/day, 20,000 document writes/day, 20,000 document deletes/day, 1 GB total storage.
- **Cost Scaling:** $0.06 per 100,000 reads; $0.18 per 100,000 writes. Highly cost-effective for bounded session chat documents with cursor pagination.

### 2.4 Cloudflare R2 Media Storage
- **Free Tier:** 10 GB storage/month, 1,000,000 Class A operations (writes)/month, 10,000,000 Class B operations (reads)/month. **Zero egress fees.**
- **Cost Beyond Free Tier:** $0.015/GB-month storage. Class A: $4.50 / million; Class B: $0.36 / million. The zero-egress policy makes R2 significantly cheaper than AWS S3.
