# Runbook: Media Storage Recovery

1. Verify Cloudflare R2 API credentials and endpoint connectivity.
2. If R2 write fails, verify the fallback local buffer has captured pending assets for asynchronous replay.
