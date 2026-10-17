"""
tests/integration/test_payment_api.py
Integration tests for FastAPI endpoints: plans catalog, current subscription, Razorpay order generation, payment verification, and webhook ingestion.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import pytest
from starlette.testclient import TestClient

from likby.domain.entities.payment import PaymentOrder
from likby.domain.entities.user import User
from likby.domain.enums import PaymentOrderStatus, PaymentProviderType, SubscriptionTier
from likby.main import app


def test_get_subscription_plans():
    """Verify GET /api/v1/subscriptions/plans returns authoritative plan catalog."""
    with TestClient(app) as client:
        response = client.get("/api/v1/subscriptions/plans")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 4

        names = [p["display_name"] for p in data]
        assert "LikBy Base" in names
        assert "LikBy Spark" in names
        assert "LikBy Premium" in names
        assert "LikBy Diamond" in names


def test_get_my_subscription_requires_auth_and_returns_limits():
    """Verify GET /api/v1/subscriptions/me enforces authentication and returns tier/limits."""
    with TestClient(app) as client:
        # 1. Unauthenticated -> 401
        res_no_auth = client.get("/api/v1/subscriptions/me")
        assert res_no_auth.status_code == 401

        # 2. Authenticated -> 200 with Base tier
        # Seed test user in db
        user_repo = app.state.user_repo
        test_user = User(id="usr_api_test_sub", telegram_id=9876543)
        import asyncio
        asyncio.run(user_repo.save(test_user))

        res = client.get(
            "/api/v1/subscriptions/me",
            headers={"X-User-Id": "usr_api_test_sub"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "usr_api_test_sub"
        assert data["tier"] == "BASE"
        assert data["tier_name"] == "LikBy Base"
        assert "likes_per_day" in data["limits"]
        assert data["limits"]["likes_per_day"] == 25


def test_create_razorpay_order_and_verify_flow():
    """Verify POST /api/v1/payments/razorpay/orders and POST /api/v1/payments/razorpay/verify."""
    with TestClient(app) as client:
        # Seed test user
        user_repo = app.state.user_repo
        test_user = User(id="usr_api_checkout", telegram_id=555444)
        import asyncio
        asyncio.run(user_repo.save(test_user))

        headers = {"X-User-Id": "usr_api_checkout"}

        # 1. Cannot create order for Base (free)
        res_base = client.post(
            "/api/v1/payments/razorpay/orders",
            headers=headers,
            json={"plan_code": "BASE"},
        )
        assert res_base.status_code == 400

        # 2. Create order for Premium (₹79 -> 7900 paise)
        res_order = client.post(
            "/api/v1/payments/razorpay/orders",
            headers=headers,
            json={"plan_code": "PREMIUM"},
        )
        assert res_order.status_code == 200
        order_data = res_order.json()
        assert order_data["amount"] == 7900
        assert order_data["currency"] == "INR"
        assert order_data["plan_code"] == "PREMIUM"

        internal_order_id = order_data["order_id"]
        razorpay_order_id = order_data["razorpay_order_id"]

        # Compute valid signature
        secret = "mock_secret"
        app.state.payment_service._razorpay._key_secret = pytest.importorskip("pydantic").SecretStr(secret)
        fake_payment_id = "pay_test_api_999"
        msg = f"{razorpay_order_id}|{fake_payment_id}".encode("utf-8")
        sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        # 3. Verify payment
        res_verify = client.post(
            "/api/v1/payments/razorpay/verify",
            headers=headers,
            json={
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": fake_payment_id,
                "razorpay_signature": sig,
            },
        )
        assert res_verify.status_code == 200
        v_data = res_verify.json()
        assert v_data["status"] == "success"
        assert v_data["tier"] == "PREMIUM"

        # 4. Check /api/v1/payments/history
        res_hist = client.get("/api/v1/payments/history", headers=headers)
        assert res_hist.status_code == 200
        history = res_hist.json()
        assert len(history) == 1
        assert history[0]["status"].lower() == "captured"
        assert history[0]["amount"] == 7900


def test_razorpay_webhook_endpoint():
    """Verify POST /api/v1/webhooks/razorpay signature verification."""
    with TestClient(app) as client:
        # Invalid signature -> 400
        res_bad = client.post(
            "/api/v1/webhooks/razorpay",
            headers={"X-Razorpay-Signature": "invalid_sig"},
            data=b'{"event": "payment.captured"}',
        )
        assert res_bad.status_code == 400
