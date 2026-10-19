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
from likby.services.progression_service import ACHIEVEMENTS_CATALOG
from likby.telegram.security import validate_telegram_init_data

router = APIRouter(prefix="/api/v1/play", tags=["LikBy Play Gaming Ecosystem"])


# =============================================================================
# Request & Response Schemas
# =============================================================================

class InviteDuelRequest(BaseModel):
    recipient_id: str = Field(..., description="Target User.id or recipient Telegram user ID")
    game_id: str = Field(..., description="Identifier for one of the registered duel games e.g. connect_four, xo")


class ActionRequest(BaseModel):
    action_type: str = Field(..., description="Action name e.g. drop_piece, strike, move, attack")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Game-specific action parameters")


class JoinQueueRequest(BaseModel):
    game_id: str = Field(..., description="Duel game ID to match for (e.g. xo, connect_four)")


class VerifyDailyRiddleRequest(BaseModel):
    answer: str = Field(..., description="User's guess for the daily cryptic riddle")
    date_str: Optional[str] = Field(None, description="Optional YYYY-MM-DD date key")


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


@router.get("/active_chat_partner")
async def get_active_chat_partner(
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """Check if the user is currently in an active conversation session with a partner."""
    session_repo = request.app.state.session_repo
    active_session = await session_repo.get_active_by_user_id(user.id)
    if not active_session:
        return {"has_partner": False, "partner_id": None, "session_id": None, "partner_name": None}

    try:
        partner_id = active_session.get_partner_id(user.id)
    except Exception:
        partner_id = None

    partner_name = "Anonymous Partner"
    if partner_id:
        profile_repo = getattr(request.app.state, "profile_repo", None)
        if profile_repo:
            partner_profile = await profile_repo.get_by_user_id(partner_id)
            if partner_profile and partner_profile.display_name:
                partner_name = partner_profile.display_name

    return {
        "has_partner": True,
        "partner_id": partner_id,
        "partner_name": partner_name,
        "session_id": active_session.id,
    }


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
    raw_id = payload.game_id.lower().strip()
    if raw_id == "tictactoe":
        raw_id = "xo"
    try:
        game_type = GameType(raw_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid game_id '{payload.game_id}'. Must be one of the registered duel games.",
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

    # Check for match completion & award progression
    unlocked_achievements: List[Dict[str, Any]] = []
    progression_summary: Optional[Dict[str, Any]] = None
    prog_service = getattr(request.app.state, "progression_service", None)

    if winner and prog_service:
        session = await play_service._play_repo.get_session(session_id)
        if session:
            score = new_state.get("score") or new_state.get("p1_score") or 0
            prog, unlocked = prog_service.record_duel_completion(
                user_id=user.id,
                game_id=session.game_id,
                is_winner=(winner == user.id),
                is_draw=(winner == "DRAW"),
                score=score,
                metadata=new_state,
            )
            unlocked_achievements = [a.model_dump() for a in unlocked]
            progression_summary = {
                "level": prog.level,
                "total_xp": prog.total_xp,
                "streak": prog.current_streak,
            }

    # Broadcast via WebSocket if active connections exist
    action_event = {
        "version": 1,
        "type": "game.action" if not winner else "game.completed",
        "session_id": session_id,
        "action_type": payload.action_type,
        "actor_id": user.id,
        "state": new_state,
        "winner_id": winner,
        "message": msg,
        "achievements": unlocked_achievements,
        "progression": progression_summary,
    }
    await manager.broadcast_to_session(session_id, action_event)

    return {
        "status": "success",
        "message": msg,
        "state": new_state,
        "winner_id": winner,
        "achievements": unlocked_achievements,
        "progression": progression_summary,
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

    # Notify old session participants of new rematch session
    await manager.broadcast_to_session(session_id, {
        "version": 1,
        "type": "game.rematch",
        "old_session_id": session_id,
        "new_session_id": new_session.id,
        "game_id": new_session.game_id.value,
    })

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
# Matchmaking Queue Endpoints
# =============================================================================

@router.post("/matchmaking/join")
async def join_matchmaking_queue(
    payload: JoinQueueRequest,
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """Enter the random opponent matchmaking queue for a specified duel game."""
    raw_id = payload.game_id.lower().strip()
    if raw_id == "tictactoe":
        raw_id = "xo"
    try:
        game_type = GameType(raw_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid duel game ID.")

    mm_service = getattr(request.app.state, "game_matchmaking_service", None)
    if not mm_service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Matchmaking unavailable.")

    ok, msg, entry = await mm_service.enqueue_player(user.id, game_type)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    status_data = mm_service.get_status(user.id)
    return {"status": "success", "message": msg, "queue": status_data}


@router.post("/matchmaking/leave")
async def leave_matchmaking_queue(
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """Leave matchmaking search queue."""
    mm_service = getattr(request.app.state, "game_matchmaking_service", None)
    if mm_service:
        await mm_service.cancel_player(user.id)
    return {"status": "success", "message": "Left matchmaking queue."}


@router.get("/matchmaking/status")
async def get_matchmaking_status(
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """Poll or query current matchmaking ticket status."""
    mm_service = getattr(request.app.state, "game_matchmaking_service", None)
    if not mm_service:
        return {"state": "DISCONNECTED"}
    return mm_service.get_status(user.id)


# =============================================================================
# Progression, Achievements & Leaderboard Endpoints
# =============================================================================

@router.get("/progression")
async def get_user_progression(
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """Retrieve player level, total XP, next level target, and win streaks."""
    prog_service = getattr(request.app.state, "progression_service", None)
    if not prog_service:
        return {"level": 1, "total_xp": 0, "xp_to_next_level": 200, "progress_percent": 0}
    return prog_service.get_user_overview(user.id)


@router.get("/achievements")
async def get_all_achievements(
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> List[Dict[str, Any]]:
    """Retrieve all GameVerse achievements and whether user has unlocked them."""
    prog_service = getattr(request.app.state, "progression_service", None)
    unlocked_ids: set = set()
    if prog_service:
        prog = prog_service.get_or_create_progression(user.id)
        unlocked_ids = prog.unlocked_achievements

    return [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "icon": a.icon,
            "xp_reward": a.xp_reward,
            "category": a.category,
            "is_unlocked": a.id in unlocked_ids,
        }
        for a in ACHIEVEMENTS_CATALOG.values()
    ]


@router.get("/leaderboard")
async def get_global_leaderboard(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
) -> List[Dict[str, Any]]:
    """Retrieve top players ranked by level and XP."""
    prog_service = getattr(request.app.state, "progression_service", None)
    if not prog_service:
        return []
    return prog_service.get_leaderboard(limit=limit)


# =============================================================================
# Solo Puzzle Generator & Daily Challenge Endpoints
# =============================================================================

@router.get("/daily_challenge")
async def get_canonical_daily_challenge(
    request: Request,
    date_str: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Retrieve the canonical Daily Mystery challenge for today (UTC)."""
    puzzle_service = getattr(request.app.state, "puzzle_generator_service", None)
    if not puzzle_service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Puzzle generator unavailable.")
    return puzzle_service.get_canonical_daily_challenge(date_str)


@router.post("/daily_challenge/verify")
async def verify_daily_challenge_solution(
    payload: VerifyDailyRiddleRequest,
    request: Request,
    user: User = Depends(get_play_authenticated_user),
) -> Dict[str, Any]:
    """Verify daily cryptic riddle solution and award XP and achievements."""
    puzzle_service = getattr(request.app.state, "puzzle_generator_service", None)
    if not puzzle_service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Puzzle generator unavailable.")

    date_str = payload.date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    is_correct, explanation = puzzle_service.verify_daily_mystery_solution(date_str, payload.answer)
    if not is_correct:
        return {"solved": False, "message": explanation}

    # Award progression and check Daily Challenger achievement
    prog_service = getattr(request.app.state, "progression_service", None)
    unlocked_achievements: List[Dict[str, Any]] = []
    if prog_service:
        _, unlocked = prog_service.record_solo_completion(
            user_id=user.id,
            game_id=GameType.DAILY_MYSTERY,
            score=100,
            metadata={"solved": True},
        )
        unlocked_achievements = [a.dict() for a in unlocked]

    return {
        "solved": True,
        "message": "🎉 Correct! Daily Mystery riddle deciphered!",
        "explanation": explanation,
        "xp_awarded": 150,
        "achievements": unlocked_achievements,
    }


@router.get("/solo/word_hunt/generate")
async def generate_word_hunt(
    request: Request,
    category: str = Query("TECH"),
    grid_size: int = Query(5, ge=5, le=8),
    seed: Optional[int] = Query(None),
) -> Dict[str, Any]:
    """Generate a verified solvable Word Hunt letter matrix."""
    puzzle_service = getattr(request.app.state, "puzzle_generator_service", None)
    if not puzzle_service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Puzzle generator unavailable.")
    return puzzle_service.generate_word_hunt_puzzle(grid_size=grid_size, category=category, seed=seed)


@router.get("/solo/color_flow/generate")
async def generate_color_flow(
    request: Request,
    grid_size: int = Query(4, ge=4, le=6),
    flow_count: int = Query(3, ge=2, le=4),
    seed: Optional[int] = Query(None),
) -> Dict[str, Any]:
    """Generate a verified solvable Color Flow board with non-overlapping routes."""
    puzzle_service = getattr(request.app.state, "puzzle_generator_service", None)
    if not puzzle_service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Puzzle generator unavailable.")
    return puzzle_service.generate_color_flow_puzzle(grid_size=grid_size, flow_count=flow_count, seed=seed)


# =============================================================================
# WebSocket Real-Time Match Hub & Protocol
# =============================================================================

class PlayConnectionManager:
    """Manages real-time WebSockets for active duel game sessions and matchmaking."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.queue_connections: Dict[str, WebSocket] = {}

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
    """Live WebSocket channel for real-time multiplayer duel game synchronization with typed protocol."""
    await manager.connect(session_id, websocket)
    # Send initial connection confirmation with versioned schema
    await websocket.send_text(json.dumps({
        "version": 1,
        "type": "game.state",
        "session_id": session_id,
        "status": "CONNECTED",
    }))
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
                msg_type = data.get("type") or data.get("event")

                if msg_type in ("connection.ping", "ping"):
                    pong_type = "pong" if msg_type == "ping" else "connection.pong"
                    await websocket.send_text(json.dumps({
                        "version": 1,
                        "type": pong_type,
                        "session_id": session_id,
                    }))
                elif msg_type == "game.ready":
                    await manager.broadcast_to_session(session_id, {
                        "version": 1,
                        "type": "game.ready",
                        "session_id": session_id,
                        "actor_id": data.get("user_id"),
                    })
                elif msg_type in ("game.input", "game.action", "action"):
                    action_payload = data.get("payload") or data.get("action") or {}
                    await manager.broadcast_to_session(session_id, {
                        "version": 1,
                        "type": "game.state",
                        "session_id": session_id,
                        "action": action_payload,
                        "sequence": data.get("sequence", 0),
                    })
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)

