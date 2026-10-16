"""
likby.domain.entities.media_asset
Media asset metadata entity for Cloudflare R2 / S3 storage tracking.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from likby.domain.enums import MediaUploadStatus


class MediaAsset(BaseModel):
    """Metadata record for binary attachments stored in object storage."""

    id: str = Field(..., description="Unique generated asset identifier (ast_...)")
    session_id: str = Field(..., description="Foreign key to ChatSession.id")
    message_id: str = Field(..., description="Foreign key to ChatMessage.id")
    storage_provider: str = Field(default="r2", description="Object storage provider (r2, local)")
    bucket: str = Field(..., description="Target storage bucket name")
    object_key: str = Field(..., description="Deterministic S3/R2 storage key")
    mime_type: str = Field(..., description="MIME classification (image/jpeg, video/mp4, etc.)")
    size_bytes: int = Field(..., ge=0, description="Payload size in bytes")
    sha256_hash: Optional[str] = Field(default=None, description="SHA-256 integrity hash")
    original_filename: Optional[str] = Field(default=None, description="Sanitized client filename")
    telegram_file_id: Optional[str] = Field(default=None, description="Telegram file handle")
    upload_status: MediaUploadStatus = Field(
        default=MediaUploadStatus.PENDING,
        description="Lifecycle archival state",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    retention_state: str = Field(default="ACTIVE", description="Retention status (ACTIVE, PURGED)")

    @classmethod
    def generate_object_key(
        cls,
        environment: str,
        session_id: str,
        message_id: str,
        asset_id: str,
        safe_filename: str,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """Construct deterministic object key following LikBy convention."""
        ts = timestamp or datetime.now(timezone.utc)
        year = ts.strftime("%Y")
        month = ts.strftime("%m")
        return f"likby/{environment}/{year}/{month}/{session_id}/{message_id}/{asset_id}_{safe_filename}"
