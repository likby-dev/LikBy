"""
tests/integration/test_api.py
Integration tests for FastAPI health check and webhook endpoints.
"""

import pytest
from starlette.testclient import TestClient
from tikible.main import app


def test_health_live():
    with TestClient(app) as client:
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_webhook_rejects_missing_or_invalid_secret_token():
    with TestClient(app) as client:
        # No header
        resp1 = client.post("/api/v1/telegram/webhook", json={"update_id": 1})
        assert resp1.status_code == 403

        # Invalid header
        resp2 = client.post(
            "/api/v1/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret-token"},
            json={"update_id": 1},
        )
        assert resp2.status_code == 403
