"""
likby.services.media_storage_service
Media storage service supporting Cloudflare R2 and local filesystem fallback.
"""

from abc import ABC, abstractmethod
import hashlib
import os
from pathlib import Path
from typing import List, Optional, Tuple
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

    @abstractmethod
    def generate_presigned_url(self, object_key: str, expires_in: int = 300) -> Optional[str]:
        """Generate a time-limited presigned URL for reading media."""
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

    def generate_presigned_url(self, object_key: str, expires_in: int = 300) -> Optional[str]:
        # Local provider mock presigned URL
        return f"/media/local/{object_key}?expires={expires_in}"


class CloudflareR2StorageProvider(MediaStorageProvider):
    """Cloudflare R2 private S3-compatible object storage provider."""

    def __init__(
        self,
        account_id: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: str = "likby-media",
        endpoint_url: Optional[str] = None,
        region: str = "auto",
    ) -> None:
        self._bucket_name = bucket_name
        self._endpoint_url = endpoint_url or (f"https://{account_id}.r2.cloudflarestorage.com" if account_id else None)
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._region = region
        self._client = None

        if self._endpoint_url and self._access_key_id and self._secret_access_key:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                region_name=self._region,
                config=Config(signature_version="s3v4"),
            )

    async def upload_bytes(self, object_key: str, data: bytes, mime_type: str) -> bool:
        if not self._client:
            return False
        import asyncio
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.put_object(
                    Bucket=self._bucket_name,
                    Key=object_key,
                    Body=data,
                    ContentType=mime_type,
                ),
            )
            return True
        except Exception:
            return False

    async def get_bytes(self, object_key: str) -> Optional[bytes]:
        if not self._client:
            return None
        import asyncio
        loop = asyncio.get_running_loop()
        try:
            resp = await loop.run_in_executor(
                None,
                lambda: self._client.get_object(Bucket=self._bucket_name, Key=object_key),
            )
            return resp["Body"].read()
        except Exception:
            return None

    async def delete(self, object_key: str) -> bool:
        if not self._client:
            return False
        import asyncio
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.delete_object(Bucket=self._bucket_name, Key=object_key),
            )
            return True
        except Exception:
            return False

    def generate_presigned_url(self, object_key: str, expires_in: int = 300) -> Optional[str]:
        if not self._client:
            return None
        try:
            return self._client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self._bucket_name, "Key": object_key},
                ExpiresIn=expires_in,
            )
        except Exception:
            return None


class SupabaseStorageProvider(MediaStorageProvider):
    """Supabase Cloud Storage bucket provider (Zero local disk storage)."""

    def __init__(self, supabase_client: Optional[object] = None, bucket_name: str = "likby-media") -> None:
        self._client = supabase_client
        self._bucket_name = bucket_name

    async def upload_bytes(self, object_key: str, data: bytes, mime_type: str) -> bool:
        if not self._client:
            return False
        import asyncio
        loop = asyncio.get_running_loop()
        try:
            def _sync_upload():
                return self._client.storage.from_(self._bucket_name).upload(
                    path=object_key,
                    file=data,
                    file_options={"content-type": mime_type, "upsert": "true"},
                )
            await loop.run_in_executor(None, _sync_upload)
            return True
        except Exception:
            return False

    async def get_bytes(self, object_key: str) -> Optional[bytes]:
        if not self._client:
            return None
        import asyncio
        loop = asyncio.get_running_loop()
        try:
            def _sync_download():
                return self._client.storage.from_(self._bucket_name).download(object_key)
            return await loop.run_in_executor(None, _sync_download)
        except Exception:
            return None

    async def delete(self, object_key: str) -> bool:
        if not self._client:
            return False
        import asyncio
        loop = asyncio.get_running_loop()
        try:
            def _sync_delete():
                return self._client.storage.from_(self._bucket_name).remove([object_key])
            await loop.run_in_executor(None, _sync_delete)
            return True
        except Exception:
            return False

    def generate_presigned_url(self, object_key: str, expires_in: int = 300) -> Optional[str]:
        if not self._client:
            return None
        try:
            res = self._client.storage.from_(self._bucket_name).create_signed_url(object_key, expires_in)
            return res.get("signedURL") or res.get("signedUrl")
        except Exception:
            return None



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

    async def get_presigned_url(
        self,
        asset_id: str,
        requesting_user_id: str,
        authorized_user_ids: List[str],
        expires_in: int = 300,
    ) -> Optional[str]:
        """
        Generate short-lived presigned URL if requesting user is authorized.
        Enforces strict IDOR/BOLA protection: only session participants or staff may access.
        """
        if requesting_user_id not in authorized_user_ids and requesting_user_id != "STAFF_MODERATOR":
            return None

        asset = await self._media_repo.get_by_id(asset_id)
        if not asset or asset.upload_status != MediaUploadStatus.ARCHIVED:
            return None

        return self._provider.generate_presigned_url(asset.object_key, expires_in=expires_in)

    async def verify_object_exists(self, asset_id: str) -> bool:
        """Verify object exists in storage provider."""
        asset = await self._media_repo.get_by_id(asset_id)
        if not asset:
            return False
        data = await self._provider.get_bytes(asset.object_key)
        return data is not None

