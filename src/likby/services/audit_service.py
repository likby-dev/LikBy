"""
likby.services.audit_service
Audit logging service for security, payments, and subscription state changes.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from likby.domain.entities.payment import AuditEvent
from likby.repositories.interfaces import AuditEventRepository


class AuditService:
    """Manages append-only audit event logging."""

    def __init__(self, audit_repo: AuditEventRepository) -> None:
        self._repo = audit_repo

    async def record(
        self,
        actor_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=f"aud_{uuid.uuid4().hex[:16]}",
            actor_id=actor_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            timestamp=datetime.now(timezone.utc),
            metadata_json=metadata or {},
        )
        await self._repo.record_event(event)
        return event

    async def get_history(self, entity_type: str, entity_id: str) -> List[AuditEvent]:
        return await self._repo.get_events_for_entity(entity_type, entity_id)
