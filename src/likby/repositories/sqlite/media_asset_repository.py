"""
likby.repositories.sqlite.media_asset_repository
aiosqlite implementation of MediaAssetRepository.
"""

from datetime import datetime
from typing import Optional
import aiosqlite
from likby.domain.entities.media_asset import MediaAsset
from likby.domain.enums import MediaUploadStatus
from likby.repositories.interfaces import MediaAssetRepository


class SqliteMediaAssetRepository(MediaAssetRepository):
    """SQLite implementation of MediaAssetRepository."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, asset: MediaAsset) -> None:
        await self._conn.execute(
            """
            INSERT INTO media_assets (
                id, session_id, message_id, storage_provider, bucket,
                object_key, mime_type, size_bytes, sha256_hash,
                original_filename, telegram_file_id, upload_status,
                created_at, retention_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                upload_status = excluded.upload_status,
                retention_state = excluded.retention_state
            """,
            (
                asset.id,
                asset.session_id,
                asset.message_id,
                asset.storage_provider,
                asset.bucket,
                asset.object_key,
                asset.mime_type,
                asset.size_bytes,
                asset.sha256_hash,
                asset.original_filename,
                asset.telegram_file_id,
                asset.upload_status.value,
                asset.created_at.isoformat(),
                asset.retention_state,
            ),
        )
        await self._conn.commit()

    async def get_by_id(self, asset_id: str) -> Optional[MediaAsset]:
        async with self._conn.execute(
            """
            SELECT id, session_id, message_id, storage_provider, bucket,
                   object_key, mime_type, size_bytes, sha256_hash,
                   original_filename, telegram_file_id, upload_status,
                   created_at, retention_state
            FROM media_assets WHERE id = ?
            """,
            (asset_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_by_message_id(self, message_id: str) -> Optional[MediaAsset]:
        async with self._conn.execute(
            """
            SELECT id, session_id, message_id, storage_provider, bucket,
                   object_key, mime_type, size_bytes, sha256_hash,
                   original_filename, telegram_file_id, upload_status,
                   created_at, retention_state
            FROM media_assets WHERE message_id = ?
            """,
            (message_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    def _row_to_entity(self, row: tuple) -> MediaAsset:
        return MediaAsset(
            id=row[0],
            session_id=row[1],
            message_id=row[2],
            storage_provider=row[3],
            bucket=row[4],
            object_key=row[5],
            mime_type=row[6],
            size_bytes=row[7],
            sha256_hash=row[8],
            original_filename=row[9],
            telegram_file_id=row[10],
            upload_status=MediaUploadStatus(row[11]),
            created_at=datetime.fromisoformat(row[12]),
            retention_state=row[13],
        )
