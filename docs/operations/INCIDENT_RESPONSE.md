# LikBy Incident Response Playbook

---

## Severity Levels

- **SEV-1 (Critical):** Bot completely down, webhooks returning 5xx, or payment activation failing globally.
- **SEV-2 (High):** Media relay failing or game sessions failing to launch.
- **SEV-3 (Medium):** Degraded latency (>2s response time) or cold start delays.
- **SEV-4 (Low):** Minor UI formatting anomaly.

---

## Emergency Kill-Switch

To temporarily pause bot interactions during maintenance or an ongoing attack:
Set environment variable `MAINTENANCE_MODE=true` in Render.
The webhook endpoint will return friendly "LikBy is undergoing scheduled maintenance" notices.
