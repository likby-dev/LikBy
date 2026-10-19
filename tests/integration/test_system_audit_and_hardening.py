"""
tests/integration/test_system_audit_and_hardening.py
Verification suite for system audit findings:
- Security headers and X-Request-Id correlation
- Telegram initData authentication age / replay attack prevention
- End-to-end endpoint authentication via X-Telegram-Init-Data header
- WebSocket authorization & intruder rejection
- Custom HTTPException handler with request ID tracking
"""

import asyncio
from datetime import datetime, timezone
import hashlib
import hmac
import json
import time
import pytest
from starlette.testclient import TestClient

from likby.config import get_settings
from likby.domain.entities.user import User
from likby.main import app
from likby.telegram.security import validate_telegram_init_data


def generate_telegram_init_data(bot_token: str, user_dict: dict, auth_date: int = None) -> str:
    """Helper to generate authentic Telegram WebAppData initData query string."""
    if auth_date is None:
        auth_date = int(time.time())

    user_json = json.dumps(user_dict, separators=(",", ":"))
    params = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": user_json,
    }
    data_check_list = [f"{k}={params[k]}" for k in sorted(params.keys())]
    data_check_string = "\n".join(data_check_list)

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    parts = [f"{k}={v}" for k, v in params.items()]
    parts.append(f"hash={calculated_hash}")
    return "&".join(parts)


def test_security_headers_and_correlation_id():
    """Verify security headers and correlation ID middleware are attached to HTTP responses."""
    with TestClient(app) as client:
        # 1. Custom request ID is preserved
        resp = client.get("/health/live", headers={"X-Request-Id": "custom_req_12345"})
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-Id") == "custom_req_12345"
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "X-Response-Time-Ms" in resp.headers

        # 2. Auto-generated request ID when omitted
        resp2 = client.get("/health/live")
        assert resp2.status_code == 200
        req_id = resp2.headers.get("X-Request-Id")
        assert req_id is not None and req_id.startswith("req_")


def test_telegram_init_data_replay_attack_rejected():
    """Verify validate_telegram_init_data rejects expired auth_date (replay protection)."""
    settings = get_settings()
    bot_token = settings.bot_token.get_secret_value()
    user_payload = {"id": 99887766, "first_name": "Auditor"}

    current_ts = int(time.time())
    stale_ts = current_ts - 100000  # > 24 hours ago (86400s)

    # 1. Stale initData fails freshness verification
    stale_raw = generate_telegram_init_data(bot_token, user_payload, auth_date=stale_ts)
    assert validate_telegram_init_data(stale_raw, bot_token) is None

    # 2. Fresh initData succeeds
    fresh_raw = generate_telegram_init_data(bot_token, user_payload, auth_date=current_ts)
    validated = validate_telegram_init_data(fresh_raw, bot_token)
    assert validated is not None
    assert validated["user"]["id"] == 99887766


def test_endpoint_authentication_via_init_data_header():
    """Verify X-Telegram-Init-Data authenticates successfully without AttributeError."""
    settings = get_settings()
    bot_token = settings.bot_token.get_secret_value()

    with TestClient(app) as client:
        user_repo = app.state.user_repo
        test_user = User(id="u_audit_initdata_1", telegram_id=77665544)
        asyncio.run(user_repo.save(test_user))

        user_payload = {"id": 77665544, "first_name": "VerifiedTgUser"}
        init_data_str = generate_telegram_init_data(bot_token, user_payload)

        # Authenticate with X-Telegram-Init-Data
        resp = client.get(
            "/api/v1/play/entitlements",
            headers={"X-Telegram-Init-Data": init_data_str},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "u_audit_initdata_1"
        assert data["tier"] == "BASE"


def test_websocket_unauthorized_intruder_rejected():
    """Verify WebSocket connection without credentials or with unauthorized identity is rejected."""
    with TestClient(app) as client:
        user_repo = app.state.user_repo
        owner = User(id="u_owner_ws_1", telegram_id=121212)
        intruder = User(id="u_intruder_ws_2", telegram_id=343434)
        asyncio.run(user_repo.save(owner))
        asyncio.run(user_repo.save(intruder))

        # Start a game session owned by owner
        resp = client.post(
            "/api/v1/play/solo/color_flow/start",
            headers={"X-User-Id": owner.id},
        )
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]

        # 1. Unauthenticated connection is rejected
        with pytest.raises(Exception):
            with client.websocket_connect(f"/api/v1/play/ws/{session_id}") as ws:
                ws.receive_json()

        # 2. Intruder connection is rejected (not a participant)
        with pytest.raises(Exception):
            with client.websocket_connect(f"/api/v1/play/ws/{session_id}?token={intruder.id}") as ws:
                ws.receive_json()

        # 3. Legitimate owner connection succeeds
        with client.websocket_connect(f"/api/v1/play/ws/{session_id}?token={owner.id}") as ws:
            init_msg = ws.receive_json()
            assert init_msg["type"] == "game.state"
            assert init_msg["session_id"] == session_id


def test_http_exception_custom_handler():
    """Verify HTTPException response has structured format and includes correlation request_id."""
    with TestClient(app) as client:
        resp = client.get("/api/v1/play/entitlements", headers={"X-Request-Id": "err_test_req_99"})
        assert resp.status_code == 401
        body = resp.json()
        assert "detail" in body
        assert body["status_code"] == 401
        assert body["request_id"] == "err_test_req_99"
