"""
likby.services.media_storage_service
Media storage service supporting Cloudflare R2 and local filesystem fallback.
"""

from abc import ABC, abstractmethod
import hashlib
import os
from pathlib import Path
from typing import Optional, Tuple
import aiofiles
from likby.domain.entities.media_asset import MediaAsset
from likby.domain.enums import MediaUploadStatus
from likby.repositories.interfaces import MediaAssetRepository


class MediaStorageProvider(ABC):
    """Abstract object storage provider interface."""

    @abstractmethod
    async def upload_bytes(self, object_key: str, data: bytes, mime_type: str) -> bool:
        """Upload raw bytes to storage destination."""
        pass

    @abstractmethod
    async def get_bytes(self, object_key: str) -> Optional[bytes]:
        """Retrieve stored bytes from storage destination."""
        pass

    @abstractmethod
    async def delete(self, object_key: str) -> bool:
        """Delete object from storage."""
        pass


class LocalMediaStorageProvider(MediaStorageProvider):
    """Local filesystem storage provider for testing and development."""

    def __init__(self, base_dir: str = "media_store") -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    async def upload_bytes(self, object_key: str, data: bytes, mime_type: str) -> bool:
        target_path = self._base_dir / object_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(target_path, "wb") as f:
            await f.write(data)
        return True

    async def get_bytes(self, object_key: str) -> Optional[bytes]:
        target_path = self._base_dir / object_key
        if not target_path.exists():
            return None
        async with aiofiles.open(target_path, "rb") as f:
            return await f.read()

    async def delete(self, object_key: str) -> bool:
        target_path = self._base_dir / object_key
        if target_path.exists():
            target_path.unlink()
            return True
        return False


class MediaService:
    """Manages media asset archival lifecycle and metadata linking."""

    def __init__(
        self,
        provider: MediaStorageProvider,
        media_repo: MediaAssetRepository,
        environment: str = "development",
        bucket_name: str = "likby-media",
    ) -> None:
        self._provider = provider
        self._media_repo = media_repo
        self._environment = environment
        self._bucket_name = bucket_name

    async def archive_media(
        self,
        asset_id: str,
        session_id: str,
        message_id: str,
        data: bytes,
        mime_type: str,
        original_filename: Optional[str] = None,
        telegram_file_id: Optional[str] = None,
    ) -> MediaAsset:
        """Archive binary media payload, calculate hash, and persist metadata."""
        safe_name = Path(original_filename or "media.bin").name.replace(" ", "_")
        object_key = MediaAsset.generate_object_key(
            environment=self._environment,
            session_id=session_id,
            message_id=message_id,
            asset_id=asset_id,
            safe_filename=safe_name,
        )

        sha256 = hashlib.sha256(data).hexdigest()
        size_bytes = len(data)

        # Upload binary
        uploaded = await self._provider.upload_bytes(object_key, data, mime_type)
        status = MediaUploadStatus.ARCHIVED if uploaded else MediaUploadStatus.FAILED

        asset = MediaAsset(
            id=asset_id,
            session_id=session_id,
            message_id=message_id,
            storage_provider="local" if isinstance(self._provider, LocalMediaStorageProvider) else "r2",
            bucket=self._bucket_name,
            object_key=object_key,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256_hash=sha256,
            original_filename=safe_name,
            telegram_file_id=telegram_file_id,
            upload_status=status,
        )

        await self._media_repo.save(asset)
        return asset

    async def retrieve_media_bytes(self, asset_id: str) -> Optional[Tuple[MediaAsset, bytes]]:
        """Retrieve media metadata and binary payload."""
        asset = await self._media_repo.get_by_id(asset_id)
        if not asset or asset.upload_status != MediaUploadStatus.ARCHIVED:
            return None
        data = await self._provider.get_bytes(asset.object_key)
        if data is None:
            return None
        return asset, data
