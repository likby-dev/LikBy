"""
tests/integration/test_sqlite_repositories.py
Integration tests for all SQLite repositories and database schema.
"""

import pytest
import aiosqlite
from likby.domain.entities.user import User
from likby.domain.entities.profile import Profile
from likby.domain.entities.match_ticket import MatchTicket
from likby.domain.entities.chat_session import ChatSession
from likby.domain.entities.game import GameSession
from likby.domain.entities.block import UserBlock
from likby.domain.entities.report import Report
from likby.domain.enums import (
    Gender,
    GenderPreference,
    ReportCategory,
    SessionStatus,
    TerminationReason,
    TicketStatus,
    UserState,
    UserStatus,
)
from likby.repositories.sqlite.database import SQLITE_SCHEMA_DDL
from likby.repositories.sqlite.user_repository import SqliteUserRepository
from likby.repositories.sqlite.profile_repository import SqliteProfileRepository
from likby.repositories.sqlite.match_ticket_repository import SqliteMatchTicketRepository
from likby.repositories.sqlite.chat_session_repository import SqliteChatSessionRepository
from likby.repositories.sqlite.game_repository import SqliteGameRepository
from likby.repositories.sqlite.block_repository import SqliteBlockRepository
from likby.repositories.sqlite.report_repository import SqliteReportRepository


@pytest.fixture
async def db_conn():
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys = ON;")
    await conn.executescript(SQLITE_SCHEMA_DDL)
    await conn.commit()
    yield conn
    await conn.close()


async def test_user_repository_crud(db_conn):
    repo = SqliteUserRepository(db_conn)
    user = User(id="usr_01", telegram_id=123456)
    await repo.save(user)

    fetched = await repo.get_by_id("usr_01")
    assert fetched is not None
    assert fetched.telegram_id == 123456
    assert fetched.state == UserState.ONBOARDING_AGE_GATE

    # Update
    user.verify_age()
    await repo.save(user)
    updated = await repo.get_by_telegram_id(123456)
    assert updated is not None
    assert updated.age_verified is True
    assert updated.state == UserState.ONBOARDING_ALIAS


async def test_profile_repository_crud(db_conn):
    from datetime import date
    user_repo = SqliteUserRepository(db_conn)
    profile_repo = SqliteProfileRepository(db_conn)

    user = User(id="usr_02", telegram_id=234567)
    await user_repo.save(user)

    profile = Profile(
        user_id="usr_02",
        display_name="Morgan",
        age=28,
        dob=date(1996, 4, 12),
        gender=Gender.FEMALE,
        location_country="United Kingdom",
        location_state="Greater London",
        location_city="London",
        relationship_intent="Dating",
        languages=["en", "fr"],
        interests=["coffee", "books"],
        preferred_gender_filter=[GenderPreference.ANY],
    )
    await profile_repo.save(profile)

    fetched = await profile_repo.get_by_user_id("usr_02")
    assert fetched is not None
    assert fetched.display_name == "Morgan"
    assert fetched.dob == date(1996, 4, 12)
    assert fetched.location_country == "United Kingdom"
    assert fetched.location_state == "Greater London"
    assert fetched.location_city == "London"
    assert fetched.relationship_intent == "Dating"
    assert fetched.languages == ["en", "fr"]
    assert fetched.interests == ["coffee", "books"]

    # Test update and automated trigger
    profile.update_location(country="France", state="Île-de-France", city="Paris")
    profile.update_relationship_intent("Casual Chat")
    await profile_repo.save(profile)

    updated = await profile_repo.get_by_user_id("usr_02")
    assert updated is not None
    assert updated.location_country == "France"
    assert updated.location_state == "Île-de-France"
    assert updated.location_city == "Paris"
    assert updated.relationship_intent == "Casual Chat"



async def test_match_ticket_repository(db_conn):
    user_repo = SqliteUserRepository(db_conn)
    ticket_repo = SqliteMatchTicketRepository(db_conn)

    user = User(id="usr_03", telegram_id=345678)
    await user_repo.save(user)

    ticket = MatchTicket(
        id="tkt_01",
        user_id="usr_03",
        user_gender=Gender.MALE,
        user_age=25,
        languages=["en"],
        interests=["gaming"],
        preferred_genders=[GenderPreference.ANY],
        min_age=20,
        max_age=30,
    )
    await ticket_repo.save(ticket)

    active = await ticket_repo.get_active_by_user_id("usr_03")
    assert active is not None
    assert active.status == TicketStatus.WAITING

    waiting_list = await ticket_repo.get_waiting_tickets(limit=10)
    assert len(waiting_list) == 1
    assert waiting_list[0].id == "tkt_01"


async def test_chat_session_repository(db_conn):
    user_repo = SqliteUserRepository(db_conn)
    session_repo = SqliteChatSessionRepository(db_conn)

    u1 = User(id="usr_a", telegram_id=101)
    u2 = User(id="usr_b", telegram_id=102)
    await user_repo.save(u1)
    await user_repo.save(u2)

    session = ChatSession(
        id="ses_01",
        user_a_id="usr_a",
        user_b_id="usr_b",
        match_score=0.75,
        match_metadata={"common_interests": ["coding"]},
    )
    await session_repo.save(session)

    active = await session_repo.get_active_by_user_id("usr_a")
    assert active is not None
    assert active.id == "ses_01"

    # End session
    session.end(ended_by="usr_a", reason=TerminationReason.USER_STOPPED)
    await session_repo.save(session)

    after_end = await session_repo.get_active_by_user_id("usr_a")
    assert after_end is None

    ended_session = await session_repo.get_by_id("ses_01")
    assert ended_session is not None
    assert ended_session.status == SessionStatus.ENDED


async def test_block_repository_bilateral(db_conn):
    user_repo = SqliteUserRepository(db_conn)
    block_repo = SqliteBlockRepository(db_conn)

    u1 = User(id="usr_blocker", telegram_id=201)
    u2 = User(id="usr_blocked", telegram_id=202)
    await user_repo.save(u1)
    await user_repo.save(u2)

    assert await block_repo.is_blocked("usr_blocker", "usr_blocked") is False

    block = UserBlock(id="blk_01", blocker_id="usr_blocker", blocked_id="usr_blocked")
    await block_repo.save(block)

    # Both directions must report blocked
    assert await block_repo.is_blocked("usr_blocker", "usr_blocked") is True
    assert await block_repo.is_blocked("usr_blocked", "usr_blocker") is True


async def test_report_repository(db_conn):
    user_repo = SqliteUserRepository(db_conn)
    report_repo = SqliteReportRepository(db_conn)

    u1 = User(id="usr_rep1", telegram_id=301)
    u2 = User(id="usr_rep2", telegram_id=302)
    await user_repo.save(u1)
    await user_repo.save(u2)

    report = Report(
        id="rep_01",
        reporter_id="usr_rep1",
        reported_id="usr_rep2",
        category=ReportCategory.SPAM,
        reason="Commercial advertising bot",
    )
    await report_repo.save(report)

    count = await report_repo.get_report_count_for_user("usr_rep2")
    assert count == 1


async def test_privacy_guarantee_no_message_text_persisted(db_conn):
    """
    CRITICAL PRIVACY TEST:
    Verifies that no database table has columns for message text or chat logs.
    """
    secret_text = "CONFIDENTIAL_PRIVATE_CHAT_PAYLOAD_XYZ"
    
    # Query schema of all tables
    async with db_conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'") as cursor:
        tables = await cursor.fetchall()
        for name, sql in tables:
            assert "message_text" not in sql.lower()
            assert "message_body" not in sql.lower()
            assert "chat_log" not in sql.lower()
            assert "content" not in sql.lower()
