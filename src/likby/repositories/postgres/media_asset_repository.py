"""
likby.repositories.postgres.media_asset_repository
asyncpg PostgreSQL / Supabase implementation of MediaAssetRepository.
"""

from typing import List, Optional
import asyncpg
from likby.domain.entities.media_asset import MediaAsset
from likby.domain.enums import MediaUploadStatus
from likby.repositories.interfaces import MediaAssetRepository


class PostgresMediaAssetRepository(MediaAssetRepository):
    """PostgreSQL implementation of MediaAssetRepository for R2 object metadata."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_id(self, asset_id: str) -> Optional[MediaAsset]:
        query = """
            SELECT id, session_id, message_id, storage_provider, bucket_name as bucket,
                   object_key, mime_type, size_bytes, sha256 as sha256_hash, original_filename,
                   telegram_file_id, upload_status, created_at, deleted_at
            FROM assets WHERE id = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, asset_id)
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_by_sha256(self, sha256_hash: str) -> Optional[MediaAsset]:
        query = """
            SELECT id, session_id, message_id, storage_provider, bucket_name as bucket,
                   object_key, mime_type, size_bytes, sha256 as sha256_hash, original_filename,
                   telegram_file_id, upload_status, created_at, deleted_at
            FROM assets WHERE sha256 = $1 LIMIT 1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, sha256_hash)
            if not row:
                return None
            return self._row_to_entity(row)

    async def list_by_session_id(self, session_id: str) -> List[MediaAsset]:
        query = """
            SELECT id, session_id, message_id, storage_provider, bucket_name as bucket,
                   object_key, mime_type, size_bytes, sha256 as sha256_hash, original_filename,
                   telegram_file_id, upload_status, created_at, deleted_at
            FROM assets WHERE session_id = $1 ORDER BY created_at ASC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, session_id)
            return [self._row_to_entity(r) for r in rows]

    async def get_by_message_id(self, message_id: str) -> Optional[MediaAsset]:
        query = """
            SELECT id, session_id, message_id, storage_provider, bucket_name as bucket,
                   object_key, mime_type, size_bytes, sha256 as sha256_hash, original_filename,
                   telegram_file_id, upload_status, created_at, deleted_at
            FROM assets WHERE message_id = $1 LIMIT 1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, message_id)
            if not row:
                return None
            return self._row_to_entity(row)

    async def save(self, asset: MediaAsset) -> None:
        query = """
            INSERT INTO assets (
                id, session_id, message_id, storage_provider, bucket_name,
                object_key, mime_type, size_bytes, sha256, original_filename,
                telegram_file_id, upload_status, created_at, deleted_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (id) DO UPDATE SET
                upload_status = EXCLUDED.upload_status,
                deleted_at = EXCLUDED.deleted_at
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
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
                asset.created_at,
                asset.deleted_at,
            )

    def _row_to_entity(self, row: asyncpg.Record) -> MediaAsset:
        return MediaAsset(
            id=row["id"],
            session_id=row["session_id"],
            message_id=row["message_id"],
            storage_provider=row["storage_provider"],
            bucket=row["bucket"],
            object_key=row["object_key"],
            mime_type=row["mime_type"],
            size_bytes=row["size_bytes"],
            sha256_hash=row["sha256_hash"],
            original_filename=row["original_filename"],
            telegram_file_id=row["telegram_file_id"],
            upload_status=MediaUploadStatus(row["upload_status"]),
            created_at=row["created_at"],
            deleted_at=row["deleted_at"],
        )
