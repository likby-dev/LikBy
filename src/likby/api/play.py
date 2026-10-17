"""
likby.api.play
FastAPI router for LikBy Play gaming ecosystem: 17 games catalogue, daily duel quotas,
invitations, actions, solo progression, and real-time WebSocket duel events.
"""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from likby.config import get_settings
from likby.domain.entities.play_game import GAME_CATALOGUE
from likby.domain.entities.user import User
from likby.domain.enums import GameType
from likby.repositories.interfaces import UserRepository
from likby.services.gaming_entitlement_service import GamingEntitlementService
from likby.services.play_game_service import PlayGameService
from likby.telegram.security import validate_telegram_init_data

router = APIRouter(prefix="/api/v1/play", tags=["LikBy Play Gaming Ecosystem"])


# =============================================================================
# Request & Response Schemas
# =============================================================================

class InviteDuelRequest(BaseModel):
    recipient_id: str = Field(..., description="Target User.id or recipient Telegram user ID")
    game_id: str = Field(..., description="Identifier for one of the 11 duel games e.g. connect_four")


class ActionRequest(BaseModel):
    action_type: str = Field(..., description="Action name e.g. drop_piece, strike, move, attack")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Game-specific action parameters")


# =============================================================================
# Authentication Dependency
# =============================================================================

async def get_play_authenticated_user(
    request: Request,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> User:
    """
    Authenticate user via cryptographic Telegram WebApp initData verification
    or via internal bearer token / X-User-Id.
    """
    settings = get_settings()
    user_repo: UserRepository = request.app.state.user_repo

    # 1. Telegram Mini App initData cryptographic validation
    if x_telegram_init_data:
        validated = validate_telegram_init_data(
            x_telegram_init_data,
            settings.telegram_bot_token.get_secret_value(),
        )
        if validated and "user" in validated and "id" in validated["user"]:
            tg_id = validated["user"]["id"]
            user = await user_repo.get_by_telegram_id(tg_id)
            if user:
                return user

    # 2. Direct user identity token / header
    user_id = x_user_id
    if not user_id and authorization and authorization.startswith("Bearer "):
        user_id = authorization.replace("Bearer ", "").strip()

    if user_id:
        user = await user_repo.get_by_id(user_id)
        if user:
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please provide valid Telegram initData or X-User-Id.",
    )


# =============================================================================
# REST Endpoints
# =============================================================================

@router.get("/catalogue")
async def get_game_catalogue() -> List[Dict[str, Any]]:
    """Retrieve the authoritative catalogue of all 17 LikBy Play games (11 Duels + 6 Solos)."""
    return [
        {
            "id": g.id.value,
            "name": g.name,
            "mode": g.mode.value,
            "category": g.category,
            "typical_duration": g.typical_duration,
            "tagline": g.tagline,
            "description": g.description,
            "min_players": g.min_players,
            "max_players": g.max_players,
        }
        for g in GAME_CATALOGUE.values()
    ]


@router.get("/entitlements")
async def get_gaming_entitlements(
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """Retrieve user's daily duel allowance, consumed credits, remaining duels, and reset time."""
    quota_service: GamingEntitlementService = request.app.state.gaming_entitlement_service
    return await quota_service.get_user_entitlements(user.id)


@router.post("/duels/invite")
async def invite_to_duel(
    payload: InviteDuelRequest,
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """
    Create a time-limited duel challenge invitation.
    Verifies that both users have remaining daily duel credits.
    Does not consume credits until the challenge is accepted.
    """
    try:
        game_type = GameType(payload.game_id.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid game_id '{payload.game_id}'. Must be one of the 11 duel games.",
        )

    play_service: PlayGameService = request.app.state.play_game_service
    ok, msg, invitation = await play_service.create_duel_invitation(
        sender_id=user.id,
        recipient_id=payload.recipient_id,
        game_id=game_type,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    return {
        "status": "success",
        "message": msg,
        "invitation_id": invitation.id,
        "expires_at": invitation.expires_at.isoformat(),
    }


@router.get("/duels/invitations/pending")
async def get_pending_invitations(
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> List[Dict[str, Any]]:
    """Retrieve all pending incoming duel challenges for the authenticated user."""
    play_service: PlayGameService = request.app.state.play_game_service
    invitations = await play_service._play_repo.get_pending_invitations_for_user(user.id)
    return [
        {
            "id": inv.id,
            "sender_id": inv.sender_id,
            "game_id": inv.game_id.value,
            "expires_at": inv.expires_at.isoformat(),
            "created_at": inv.created_at.isoformat(),
        }
        for inv in invitations
    ]


@router.post("/duels/invitations/{invitation_id}/accept")
async def accept_duel_invitation(
    invitation_id: str,
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """
    Accept duel invitation.
    Atomically verifies eligibility and consumes 1 duel credit from BOTH participants.
    Returns active session ID for gameplay.
    """
    play_service: PlayGameService = request.app.state.play_game_service
    ok, msg, session = await play_service.accept_invitation(invitation_id, user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    return {
        "status": "success",
        "message": msg,
        "session_id": session.id,
        "game_id": session.game_id.value,
    }


@router.post("/duels/invitations/{invitation_id}/reject")
async def reject_duel_invitation(
    invitation_id: str,
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """Reject duel invitation. No credits are consumed."""
    play_service: PlayGameService = request.app.state.play_game_service
    ok, msg = await play_service.reject_invitation(invitation_id, user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    return {"status": "success", "message": msg}


@router.post("/solo/{game_id}/start")
async def start_solo_game(
    game_id: str,
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """
    Start a solo game experience.
    Solo games NEVER consume duel credits and are completely unlimited for every tier.
    """
    try:
        game_type = GameType(game_id.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown game ID.")

    play_service: PlayGameService = request.app.state.play_game_service
    ok, msg, session = await play_service.start_solo_game(user.id, game_type)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    return {
        "status": "success",
        "message": msg,
        "session_id": session.id,
        "game_id": session.game_id.value,
        "initial_state": session.state_data,
    }


@router.get("/duels/{session_id}/state")
async def get_duel_state(
    session_id: str,
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """Retrieve authorized sanitized game state concealing opponent-only private data."""
    play_service: PlayGameService = request.app.state.play_game_service
    ok, msg, data = await play_service.get_authorized_session_state(session_id, user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg)
    return data


@router.post("/duels/{session_id}/action")
async def submit_duel_action(
    session_id: str,
    payload: ActionRequest,
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """Execute authoritative player move or action against game rules."""
    play_service: PlayGameService = request.app.state.play_game_service
    ok, msg, new_state, winner = await play_service.submit_action(
        session_id=session_id,
        user_id=user.id,
        action_type=payload.action_type,
        action_payload=payload.payload,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    # Broadcast via WebSocket if active connections exist
    await manager.broadcast_to_session(session_id, {
        "event": "game.action",
        "action_type": payload.action_type,
        "actor_id": user.id,
        "state": new_state,
        "winner_id": winner,
        "message": msg,
    })

    return {
        "status": "success",
        "message": msg,
        "state": new_state,
        "winner_id": winner,
    }


@router.post("/duels/{session_id}/rematch")
async def request_duel_rematch(
    session_id: str,
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """Request a rematch for a completed duel. Consumes 1 credit from each participant."""
    play_service: PlayGameService = request.app.state.play_game_service
    ok, msg, new_session = await play_service.request_rematch(session_id, user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    return {
        "status": "success",
        "message": msg,
        "session_id": new_session.id,
        "game_id": new_session.game_id.value,
    }


@router.get("/stats/me")
async def get_my_game_stats(
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> List[Dict[str, Any]]:
    """Retrieve personal game statistics across all played games."""
    play_service: PlayGameService = request.app.state.play_game_service
    stats = await play_service._play_repo.get_user_statistics(user.id)
    return [
        {
            "game_id": s.game_id.value,
            "games_played": s.games_played,
            "wins": s.wins,
            "losses": s.losses,
            "draws": s.draws,
            "high_score": s.high_score,
            "last_played_at": s.last_played_at.isoformat(),
        }
        for s in stats
    ]


# =============================================================================
# WebSocket Real-Time Match Hub
# =============================================================================

class PlayConnectionManager:
    """Manages real-time WebSockets for active duel game sessions."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        if session_id in self.active_connections:
            for connection in list(self.active_connections[session_id]):
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    pass


manager = PlayConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_duel_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(None),
) -> None:
    """Live WebSocket channel for real-time multiplayer duel game synchronization."""
    await manager.connect(session_id, websocket)
    # Send initial connection confirmation
    await websocket.send_text(json.dumps({
        "event": "game.state",
        "type": "game.state",
        "session_id": session_id,
        "status": "CONNECTED",
    }))
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
                event_type = data.get("event") or data.get("type")
                if event_type == "ping":
                    await websocket.send_text(json.dumps({"event": "pong", "type": "pong"}))
                elif event_type == "game.ready":
                    await manager.broadcast_to_session(session_id, {
                        "event": "game.ready",
                        "type": "game.ready",
                        "session_id": session_id,
                    })
                elif event_type in ("game.action", "action"):
                    action_payload = data.get("action") or data.get("payload") or {}
                    await manager.broadcast_to_session(session_id, {
                        "event": "game.state",
                        "type": "game.state",
                        "session_id": session_id,
                        "action": action_payload,
                    })
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
