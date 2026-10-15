"""
tests/integration/test_unique_id_repositories.py
Integration tests for Unique ID database persistence, case-insensitive retrieval, and uniqueness constraints.
"""

import pytest
import aiosqlite
from tikible.domain.entities.user import User
from tikible.domain.entities.profile import Profile
from tikible.domain.enums import Gender, GenderPreference
from tikible.repositories.sqlite.database import SQLITE_SCHEMA_DDL
from tikible.repositories.sqlite.user_repository import SqliteUserRepository
from tikible.repositories.sqlite.profile_repository import SqliteProfileRepository


@pytest.fixture
async def db_conn():
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys = ON;")
    await conn.executescript(SQLITE_SCHEMA_DDL)
    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_unique_id ON users(unique_id);")
    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_unique_id ON profiles(unique_id);")
    await conn.commit()
    yield conn
    await conn.close()


@pytest.mark.asyncio
async def test_user_unique_id_persistence_and_case_insensitive_lookup(db_conn) -> None:
    """Verify unique_id can be saved and found regardless of casing."""
    user_repo = SqliteUserRepository(db_conn)
    user = User(id="usr_test_1", telegram_id=111222, unique_id="alex_99")
    await user_repo.save(user)

    # Exact match
    found = await user_repo.get_by_unique_id("alex_99")
    assert found is not None
    assert found.id == "usr_test_1"
    assert found.unique_id == "alex_99"

    # Case-insensitive match (e.g. searching 'ALEX_99' or 'Alex_99')
    found_upper = await user_repo.get_by_unique_id("ALEX_99")
    assert found_upper is not None
    assert found_upper.id == "usr_test_1"

    # With leading @ stripped
    found_at = await user_repo.get_by_unique_id("@alex_99")
    assert found_at is not None
    assert found_at.id == "usr_test_1"


@pytest.mark.asyncio
async def test_duplicate_display_names_in_sqlite(db_conn) -> None:
    """Verify multiple users can have the same display_name without any DB collision."""
    user_repo = SqliteUserRepository(db_conn)
    profile_repo = SqliteProfileRepository(db_conn)

    u1 = User(id="usr_01", telegram_id=101, unique_id="alpha_wolf")
    u2 = User(id="usr_02", telegram_id=102, unique_id="beta_fox")
    await user_repo.save(u1)
    await user_repo.save(u2)

    # Both users have the exact same display_name ("Alex")
    p1 = Profile(
        user_id="usr_01",
        unique_id="alpha_wolf",
        display_name="Alex",
        age=22,
        gender=Gender.MALE,
    )
    p2 = Profile(
        user_id="usr_02",
        unique_id="beta_fox",
        display_name="Alex",
        age=30,
        gender=Gender.FEMALE,
    )
    await profile_repo.save(p1)
    await profile_repo.save(p2)

    loaded_p1 = await profile_repo.get_by_user_id("usr_01")
    loaded_p2 = await profile_repo.get_by_user_id("usr_02")
    assert loaded_p1 is not None and loaded_p2 is not None
    assert loaded_p1.display_name == loaded_p2.display_name == "Alex"
    assert loaded_p1.unique_id == "alpha_wolf"
    assert loaded_p2.unique_id == "beta_fox"


@pytest.mark.asyncio
async def test_duplicate_unique_id_rejected_in_database(db_conn) -> None:
    """Verify SQLite UNIQUE constraint rejects duplicate unique_id for users."""
    user_repo = SqliteUserRepository(db_conn)

    u1 = User(id="usr_01", telegram_id=101, unique_id="cool_handle")
    await user_repo.save(u1)

    # Attempt to create another user with the identical unique_id
    u2 = User(id="usr_02", telegram_id=102, unique_id="cool_handle")
    with pytest.raises(aiosqlite.IntegrityError):
        await user_repo.save(u2)
