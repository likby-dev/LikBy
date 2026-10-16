"""
tests.unit.test_media_archival
Unit tests for deterministic R2/S3 object key formatting and media archival.
"""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from likby.domain.entities.media_asset import MediaAsset
from likby.domain.enums import MediaUploadStatus
from likby.services.media_storage_service import LocalMediaStorageProvider, MediaService
from likby.repositories.sqlite.media_asset_repository import SqliteMediaAssetRepository
from likby.repositories.sqlite.database import init_sqlite_db


def test_deterministic_object_key_generation():
    """Verify deterministic S3/R2 path construction matching Section 7."""
    fixed_ts = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
    key = MediaAsset.generate_object_key(
        environment="prod",
        session_id="cs_01K8XYZ",
        message_id="msg_01K8ABC",
        asset_id="ast_01K8DEF",
        safe_filename="photo.jpg",
        timestamp=fixed_ts,
    )
    assert key == "likby/prod/2026/10/cs_01K8XYZ/msg_01K8ABC/ast_01K8DEF_photo.jpg"


@pytest.mark.asyncio
async def test_media_archival_and_hash_calculation(tmp_path):
    """Verify binary data archival, SHA-256 calculation, and local retrieval."""
    db_file = tmp_path / "test_media.db"
    conn = await init_sqlite_db(str(db_file))
    media_repo = SqliteMediaAssetRepository(conn)

    storage = LocalMediaStorageProvider(base_dir=tmp_path / "media_store")
    service = MediaService(provider=storage, media_repo=media_repo)

    # Insert prerequisite users and session for foreign keys
    from likby.domain.entities.user import User
    from likby.domain.entities.chat_session import ChatSession
    from likby.repositories.sqlite.user_repository import SqliteUserRepository
    from likby.repositories.sqlite.chat_session_repository import SqliteChatSessionRepository

    u_repo = SqliteUserRepository(conn)
    s_repo = SqliteChatSessionRepository(conn)
    await u_repo.save(User(id="u_med1", telegram_id=301))
    await u_repo.save(User(id="u_med2", telegram_id=302))
    await s_repo.save(ChatSession(id="cs_test_01", user_a_id="u_med1", user_b_id="u_med2"))

    payload = b"TEST_IMAGE_BINARY_DATA_12345"
    asset = await service.archive_media(
        asset_id="ast_test_01",
        session_id="cs_test_01",
        message_id="msg_test_01",
        data=payload,
        mime_type="image/jpeg",
        original_filename="../../malicious_path/image.jpg",
    )

    # Path traversal must be sanitized
    assert ".." not in asset.object_key
    assert "malicious_path" not in asset.object_key
    assert asset.original_filename == "image.jpg"
    assert asset.upload_status == MediaUploadStatus.ARCHIVED
    assert asset.size_bytes == len(payload)
    assert len(asset.sha256_hash) == 64

    # Verify retrieval
    retrieved = await service.retrieve_media_bytes(asset.id)
    assert retrieved is not None
    retrieved_asset, retrieved_bytes = retrieved
    assert retrieved_bytes == payload

    await conn.close()
