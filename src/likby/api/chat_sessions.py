"""
likby.api.chat_sessions
REST endpoints for Chat Session Transcripts, Messages, Events, and Summaries.
Provides authorized access to human-readable transcripts and structured Firestore data.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from likby.config import get_settings
from likby.domain.entities.user import User
from likby.repositories.interfaces import ChatSessionRepository, UserRepository
from likby.services.transcript_service import TranscriptService
from likby.telegram.security import validate_telegram_init_data

router = APIRouter(prefix="/api/v1/chat-sessions", tags=["chat-sessions"])


# =============================================================================
# Authentication & Authorization Dependency
# =============================================================================

async def get_authenticated_chat_user(
    request: Request,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> User:
    """
    Authenticate user via cryptographic Telegram WebApp initData verification
    or via internal X-User-Id / Bearer token.
    """
    settings = get_settings()
    user_repo: UserRepository = request.app.state.user_repo

    # 1. Telegram Mini App initData cryptographic validation
    if x_telegram_init_data:
        validated = validate_telegram_init_data(
            x_telegram_init_data,
            settings.bot_token.get_secret_value(),
        )
        if not validated or "user" not in validated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid cryptographic Telegram signature in initData.",
            )
        tg_id = validated["user"].get("id")
        user = await user_repo.get_by_telegram_id(tg_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found.",
            )
        return user

    # 2. X-User-Id or Bearer token header
    target_uid = x_user_id
    if not target_uid and authorization and authorization.startswith("Bearer "):
        target_uid = authorization.replace("Bearer ", "").strip()

    if target_uid:
        user = await user_repo.get_by_id(target_uid)
        if user:
            return user
        # Allow service/admin role if target_uid == "admin" or "service_role"
        if target_uid in ("admin", "service_role"):
            return User(id=target_uid, telegram_id=0, unique_id="admin")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not recognized.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials missing (X-User-Id or X-Telegram-Init-Data required).",
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/{session_id}/transcript")
async def get_session_transcript(
    session_id: str,
    request: Request,
    format: str = Query("text", pattern="^(text|json)$"),
    user: User = Depends(get_authenticated_chat_user),
):
    """
    Retrieve human-readable chat transcript.
    Returns plain text by default, or JSON format if requested.
    Enforces participant authorization boundary.
    """
    session_repo: ChatSessionRepository = request.app.state.session_repo
    session = await session_repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")

    # Authorization
    is_admin = user.id in ("admin", "service_role")
    if not is_admin and user.id not in (session.user_a_id, session.user_b_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not an authorized participant in this session.",
        )

    transcript_service: TranscriptService = request.app.state.transcript_service
    rendered = await transcript_service.get_session_transcript(
        session_id=session_id,
        requesting_user_id=user.id,
        is_staff=is_admin,
    )
    if not rendered:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript unavailable.")

    if format == "json":
        return {
            "session_id": session_id,
            "status": session.status.value if hasattr(session.status, "value") else str(session.status),
            "transcript": rendered,
        }

    return Response(content=rendered, media_type="text/plain; charset=utf-8")


@router.get("/{session_id}/summary")
async def get_session_summary(
    session_id: str,
    request: Request,
    user: User = Depends(get_authenticated_chat_user),
) -> Dict[str, Any]:
    """Retrieve authoritative session status, participant IDs, and message/media counters."""
    session_repo: ChatSessionRepository = request.app.state.session_repo
    session = await session_repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")

    is_admin = user.id in ("admin", "service_role")
    if not is_admin and user.id not in (session.user_a_id, session.user_b_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    transcript_service: TranscriptService = request.app.state.transcript_service
    summary = await transcript_service.get_transcript_summary(
        session_id=session_id,
        requesting_user_id=user.id,
        is_staff=is_admin,
    )
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary unavailable.")
    return summary


@router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_authenticated_chat_user),
) -> Dict[str, Any]:
    """Retrieve paginated chronological messages for a chat session."""
    session_repo: ChatSessionRepository = request.app.state.session_repo
    session = await session_repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")

    is_admin = user.id in ("admin", "service_role")
    if not is_admin and user.id not in (session.user_a_id, session.user_b_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    message_repo = request.app.state.message_repo
    messages = await message_repo.get_session_messages(session_id, limit=limit, offset=offset)

    return {
        "session_id": session_id,
        "offset": offset,
        "limit": limit,
        "messages": [
            {
                "message_id": m.id,
                "sequence_number": m.sequence,
                "sender_user_id": m.sender_id,
                "sender_display_id": m.sender_display_id,
                "message_type": m.message_type.value,
                "text": m.text,
                "asset_id": m.media_asset_id,
                "delivery_status": m.delivery_status.value,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.get("/{session_id}/events")
async def get_session_events(
    session_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_authenticated_chat_user),
) -> Dict[str, Any]:
    """Retrieve paginated chronological system events for a chat session."""
    session_repo: ChatSessionRepository = request.app.state.session_repo
    session = await session_repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")

    is_admin = user.id in ("admin", "service_role")
    if not is_admin and user.id not in (session.user_a_id, session.user_b_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    message_repo = request.app.state.message_repo
    events = []
    if hasattr(message_repo, "get_session_events"):
        events = await message_repo.get_session_events(session_id, limit=limit, offset=offset)

    return {
        "session_id": session_id,
        "offset": offset,
        "limit": limit,
        "events": [
            {
                "event_id": e.id,
                "event_type": e.event_type,
                "display_text": e.display_text,
                "sequence_number": e.sequence,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }
