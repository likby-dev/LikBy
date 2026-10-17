"""
tests/integration/test_play_api.py
Integration tests for LikBy Play API, Telegram initData verification,
REST endpoints, and real-time WebSockets.
"""

import asyncio
from datetime import datetime, timezone
import hashlib
import hmac
import json
import pytest
from starlette.testclient import TestClient

from likby.config import get_settings
from likby.domain.entities.user import User
from likby.domain.enums import GameType, SubscriptionTier
from likby.main import app
from likby.telegram.security import validate_telegram_init_data


def generate_valid_telegram_init_data(bot_token: str, user_dict: dict, auth_date: int = None) -> str:
    """Helper to generate authentic Telegram WebAppData initData query string."""
    if auth_date is None:
        auth_date = int(datetime.now(timezone.utc).timestamp())

    user_json = json.dumps(user_dict, separators=(",", ":"))
    params = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": user_json,
    }
    # Sort alphabetically
    data_check_list = [f"{k}={params[k]}" for k in sorted(params.keys())]
    data_check_string = "\n".join(data_check_list)

    # Secret key
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    # Query string format
    parts = [f"{k}={v}" for k, v in params.items()]
    parts.append(f"hash={calculated_hash}")
    return "&".join(parts)


def test_telegram_init_data_cryptographic_verification():
    settings = get_settings()
    bot_token = settings.bot_token.get_secret_value()
    user_payload = {"id": 11223344, "first_name": "Alex", "username": "alex_play"}

    # 1. Valid initData succeeds
    valid_raw = generate_valid_telegram_init_data(bot_token, user_payload)
    parsed = validate_telegram_init_data(valid_raw, bot_token)
    assert parsed is not None
    assert parsed["user"]["id"] == 11223344
    assert parsed["user"]["first_name"] == "Alex"

    # 2. Tampered initData (hash mismatch) fails
    tampered_raw = valid_raw.replace("Alex", "EveAttacker")
    assert validate_telegram_init_data(tampered_raw, bot_token) is None

    # 3. Forged hash fails
    forged_raw = valid_raw.split("&hash=")[0] + "&hash=00112233445566778899aabbccddeeff"
    assert validate_telegram_init_data(forged_raw, bot_token) is None


def test_catalogue_returns_exact_17_games():
    with TestClient(app) as client:
        resp = client.get("/api/v1/play/catalogue")
        assert resp.status_code == 200
        catalogue = resp.json()
        assert len(catalogue) == 17

        game_ids = [g["id"] for g in catalogue]
        # 11 duels
        assert "carrom_clash" in game_ids
        assert "air_rush" in game_ids
        assert "pocket_pool" in game_ids
        assert "stick_arena" in game_ids
        assert "quickdraw" in game_ids
        assert "word_rush" in game_ids
        assert "brain_blitz" in game_ids
        assert "reflex_rush" in game_ids
        assert "connect_four" in game_ids
        assert "mindmatch" in game_ids
        assert "mystery_mission" in game_ids
        # 6 solos
        assert "zen_merge" in game_ids
        assert "word_hunt" in game_ids
        assert "color_flow" in game_ids
        assert "pocket_golf" in game_ids
        assert "reflex_lab" in game_ids
        assert "daily_mystery" in game_ids


def test_play_auth_and_entitlements():
    with TestClient(app) as client:
        # Unauthenticated request
        resp_unauth = client.get("/api/v1/play/entitlements")
        assert resp_unauth.status_code == 401

        # Seed test user
        user_repo = app.state.user_repo
        test_user = User(id="user_play_auth_1", telegram_id=55667788)
        asyncio.run(user_repo.save(test_user))

        # Authenticate with X-User-Id
        resp = client.get(
            "/api/v1/play/entitlements",
            headers={"X-User-Id": "user_play_auth_1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user_play_auth_1"
        assert data["tier"] == "BASE"
        assert data["daily_duels_limit"] == 5
        assert data["daily_duels_remaining"] == 5
        assert data["solo_games_unlimited"] is True


def test_invitation_lifecycle_and_duel_start():
    import uuid
    suffix = uuid.uuid4().hex[:6]
    uid_a = f"u_inv_a_{suffix}"
    uid_b = f"u_inv_b_{suffix}"

    with TestClient(app) as client:
        user_repo = app.state.user_repo
        user_a = User(id=uid_a, telegram_id=int(f"10{uuid.uuid4().int % 100000}"))
        user_b = User(id=uid_b, telegram_id=int(f"20{uuid.uuid4().int % 100000}"))
        asyncio.run(user_repo.save(user_a))
        asyncio.run(user_repo.save(user_b))

        # 1. User A creates invitation for User B to play Connect Four
        resp_inv = client.post(
            "/api/v1/play/duels/invite",
            headers={"X-User-Id": uid_a},
            json={"game_id": "connect_four", "recipient_id": uid_b},
        )
        assert resp_inv.status_code == 200
        inv_data = resp_inv.json()
        inv_id = inv_data["invitation_id"]
        assert inv_data["status"] == "success"

        # Neither user has had their quota consumed yet!
        ent_a = client.get("/api/v1/play/entitlements", headers={"X-User-Id": uid_a}).json()
        assert ent_a["daily_duels_remaining"] == 5

        # 2. User B accepts the invitation
        resp_accept = client.post(
            f"/api/v1/play/duels/invitations/{inv_id}/accept",
            headers={"X-User-Id": uid_b},
        )
        assert resp_accept.status_code == 200
        session_data = resp_accept.json()
        session_id = session_data["session_id"]
        assert session_data["status"] == "success"

        # 3. Verify atomic quota consumption: both players consumed 1 credit!
        ent_a_after = client.get("/api/v1/play/entitlements", headers={"X-User-Id": uid_a}).json()
        ent_b_after = client.get("/api/v1/play/entitlements", headers={"X-User-Id": uid_b}).json()
        assert ent_a_after["daily_duels_remaining"] == 4
        assert ent_b_after["daily_duels_remaining"] == 4

        # 4. Fetch sanitized session state
        resp_sess = client.get(
            f"/api/v1/play/duels/{session_id}/state",
            headers={"X-User-Id": uid_a},
        )
        assert resp_sess.status_code == 200
        state = resp_sess.json()
        assert state["game_id"] == "connect_four"
        assert "board" in state["game_state"]

        # 5. User A submits valid action (drop piece in col 3)
        resp_act = client.post(
            f"/api/v1/play/duels/{session_id}/action",
            headers={"X-User-Id": uid_a},
            json={"action_type": "drop_piece", "payload": {"column": 3}},
        )
        assert resp_act.status_code == 200
        updated = resp_act.json()
        assert updated["state"]["current_turn"] == uid_b


def test_solo_game_lifecycle_zero_quota_consumed():
    import uuid
    solo_uid = f"u_solo_{uuid.uuid4().hex[:6]}"
    with TestClient(app) as client:
        user_repo = app.state.user_repo
        solo_user = User(id=solo_uid, telegram_id=int(f"30{uuid.uuid4().int % 100000}"))
        asyncio.run(user_repo.save(solo_user))

        # Check initial quota
        ent_before = client.get("/api/v1/play/entitlements", headers={"X-User-Id": solo_uid}).json()
        assert ent_before["daily_duels_remaining"] == 5

        # Start solo Zen Merge
        resp_start = client.post(
            "/api/v1/play/solo/zen_merge/start",
            headers={"X-User-Id": solo_uid},
        )
        assert resp_start.status_code == 200
        session_data = resp_start.json()
        session_id = session_data["session_id"]
        assert session_data["status"] == "success"
        assert session_data["game_id"] == "zen_merge"

        # Quota remains completely untouched!
        ent_after = client.get("/api/v1/play/entitlements", headers={"X-User-Id": solo_uid}).json()
        assert ent_after["daily_duels_remaining"] == 5

        # Submit move action (try directions until valid slide)
        resp_act = None
        for d in ("left", "right", "up", "down"):
            resp_act = client.post(
                f"/api/v1/play/duels/{session_id}/action",
                headers={"X-User-Id": solo_uid},
                json={"action_type": "slide", "payload": {"direction": d}},
            )
            if resp_act.status_code == 200:
                break
        assert resp_act is not None and resp_act.status_code == 200


def test_play_websocket_connection_and_events():
    import uuid
    ws_uid = f"u_ws_{uuid.uuid4().hex[:6]}"
    with TestClient(app) as client:
        user_repo = app.state.user_repo
        ws_user = User(id=ws_uid, telegram_id=int(f"40{uuid.uuid4().int % 100000}"))
        asyncio.run(user_repo.save(ws_user))

        # Start solo game to obtain session_id
        resp = client.post(
            "/api/v1/play/solo/color_flow/start",
            headers={"X-User-Id": ws_uid},
        )
        session_id = resp.json()["session_id"]

        # Connect WebSocket with user_id header or query
        with client.websocket_connect(f"/api/v1/play/ws/{session_id}?token={ws_uid}") as websocket:
            # Receive initial state event
            init_msg = websocket.receive_json()
            assert init_msg["type"] == "game.state"
            assert init_msg["session_id"] == session_id

            # Send ping
            websocket.send_json({"type": "ping"})
            pong_msg = websocket.receive_json()
            assert pong_msg["type"] == "pong"

            # Send game.action
            websocket.send_json({
                "type": "game.action",
                "action": {
                    "color_id": "cyan",
                    "path": [{"r": 0, "c": 0}, {"r": 0, "c": 1}],
                },
            })
            state_msg = websocket.receive_json()
            assert state_msg["type"] == "game.state"


def test_static_play_app_served():
    with TestClient(app) as client:
        # 1. HTML index
        resp = client.get("/play/")
        assert resp.status_code == 200
        assert "LikBy Play" in resp.text
        assert "Every connection has a game." in resp.text

        # 2. CSS
        css_resp = client.get("/play/styles.css")
        assert css_resp.status_code == 200
        assert "--likby-bg" in css_resp.text

        # 3. JS
        js_resp = client.get("/play/app.js")
        assert js_resp.status_code == 200
        assert "LIKBY PLAY" in js_resp.text

