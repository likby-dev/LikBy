# LikBy Operations Runbook

---

## Daily & Weekly Standard Operating Procedures

1. **Health Verification:** Monitor `GET /health/ready` to ensure database and storage connections are healthy.
2. **Quota Reset Audit:** Verify at 00:05 UTC that daily quota ledgers have rolled over cleanly.
3. **Log Review:** Check for elevated 4xx/5xx responses in structured JSON logs.
