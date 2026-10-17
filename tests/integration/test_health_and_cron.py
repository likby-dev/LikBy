"""
tests/integration/test_health_and_cron.py
Integration tests for /health/ready, /health/live, cron jobs, background workers, and metrics.
"""

from datetime import datetime, timedelta, timezone
import pytest
from starlette.testclient import TestClient

from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.connection_request import ConnectionRequest
from likby.domain.entities.match_ticket import MatchTicket
from likby.domain.entities.subscription import PLAN_SPECS, SubscriptionEntitlement
from likby.domain.enums import (
    ConnectionRequestStatus,
    Gender,
    GenderPreference,
    SessionStatus,
    SubscriptionTier,
    TicketStatus,
)
from likby.main import app


def test_health_live_and_health_alias():
    """Verify GET /health/live and GET /health return 200 OK."""
    with TestClient(app) as client:
        res1 = client.get("/health/live")
        assert res1.status_code == 200
        assert res1.json()["status"] == "ok"

        res2 = client.get("/health")
        assert res2.status_code == 200
        assert res2.json()["status"] == "healthy"


def test_health_ready_diagnostics_and_workers():
    """Verify GET /health/ready checks database, storage, workers, and cron."""
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "ready"
        assert "checks" in data
        assert data["checks"]["database"] == "healthy"
        assert "storage" in data["checks"]
        assert "background_workers" in data["checks"]
        assert "cron_jobs" in data["checks"]
        assert "telegram_api" in data["checks"]

        # Check workers reporting
        assert "workers" in data
        assert data["workers"]["matchmaker"] == "running"
        assert data["workers"]["outbox"] == "running"
        assert data["workers"]["maintenance_cron"] == "running"

        # Check ready alias
        alias_res = client.get("/ready")
        assert alias_res.status_code == 200
        assert alias_res.json()["status"] == "ready"


def test_health_ready_cron_trigger():
    """Verify GET /health/ready?cron=true executes maintenance cycle and returns results."""
    with TestClient(app) as client:
        response = client.get("/health/ready?cron=true")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "ready"
        assert "cron" in data
        assert "trigger_execution" in data["cron"]
        exec_res = data["cron"]["trigger_execution"]
        assert "tickets_reaped" in exec_res
        assert "sessions_reaped" in exec_res
        assert "subscriptions_reconciled" in exec_res


def test_cron_maintenance_endpoint_and_status():
    """Verify POST /api/v1/cron/maintenance and GET /api/v1/cron/status."""
    with TestClient(app) as client:
        # 1. Trigger maintenance via API
        post_res = client.post("/api/v1/cron/maintenance")
        assert post_res.status_code == 200
        post_data = post_res.json()
        assert post_data["status"] == "success"
        assert "result" in post_data

        # 2. Inspect telemetry via GET /api/v1/cron/status
        status_res = client.get("/api/v1/cron/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["runs_total"] >= 1
        assert status_data["status"] == "healthy"
        assert status_data["last_run"] is not None


def test_cron_reaps_expired_entities():
    """Verify that the maintenance cron accurately reaps expired tickets and subscriptions."""
    with TestClient(app) as client:
        conn = app.state.db_conn
        ticket_repo = app.state.dp["ticket_repo"]
        sub_repo = app.state.subscription_service._repo
        cron_service = app.state.cron_service

        now = datetime.now(timezone.utc)
        past_time = now - timedelta(hours=2)

        # 0. Seed test user
        user_repo = app.state.user_repo
        from likby.domain.entities.user import User
        test_user = User(id="usr_expired_01", telegram_id=999888777)
        import asyncio
        asyncio.run(user_repo.save(test_user))

        # 1. Seed expired match ticket
        expired_ticket = MatchTicket(
            id="ticket_expired_test_01",
            user_id="usr_expired_01",
            user_gender=Gender.MALE,
            user_age=25,
            languages=["en"],
            interests=["coding"],
            preferred_genders=[GenderPreference.ANY],
            min_age=18,
            max_age=30,
            status=TicketStatus.WAITING,
            created_at=past_time - timedelta(minutes=10),
            expires_at=past_time,
        )
        import asyncio
        asyncio.run(ticket_repo.save(expired_ticket))

        # 2. Seed expired Spark subscription
        expired_sub = SubscriptionEntitlement(
            user_id="usr_expired_01",
            tier=SubscriptionTier.SPARK,
            max_friends=5,
            daily_searches_limit=25,
            daily_requests_limit=10,
            daily_likes_limit=50,
            daily_games_limit=10,
            daily_icebreakers_limit=5,
            starts_at=past_time - timedelta(days=1),
            expires_at=past_time,
            is_active=True,
        )
        asyncio.run(sub_repo.save(expired_sub))

        # 3. Trigger maintenance cron via endpoint
        post_res = client.post("/api/v1/cron/maintenance")
        assert post_res.status_code == 200
        results = post_res.json()["result"]
        assert results["tickets_reaped"] >= 1
        assert results["subscriptions_reconciled"] >= 1

        # 4. Verify in DB
        reaped_ticket = asyncio.run(ticket_repo.get_by_id("ticket_expired_test_01"))
        assert reaped_ticket.status == TicketStatus.EXPIRED

        reaped_sub = asyncio.run(sub_repo.get_by_user_id("usr_expired_01"))
        assert reaped_sub.tier == SubscriptionTier.BASE


def test_prometheus_metrics_endpoint():
    """Verify GET /metrics returns standard Prometheus plain-text metrics."""
    with TestClient(app) as client:
        res = client.get("/metrics")
        assert res.status_code == 200
        assert "text/plain" in res.headers["content-type"]
        body = res.text
        assert "likby_http_requests_total" in body
        assert "likby_cron_runs_total" in body
        assert "likby_database_status 1" in body
