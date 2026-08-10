"""
routes/team_ws.py
WebSocket channel for team presence, code sync, voice signaling, and live notifications.
"""

import asyncio
import json
import logging
from typing import Dict, Set, Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from database.connection import SessionLocal
from models.session import ChallengeSession
from models.team import Team
from models.team_member import TeamMember

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teams", tags=["team-ws"])

# In-memory registry: team_id -> set of (user_id, WebSocket)
_team_connections: Dict[int, Set[Tuple[int, WebSocket]]] = {}


def _get_team_sockets(team_id: int) -> Set[Tuple[int, WebSocket]]:
    return _team_connections.get(team_id, set())


async def _send_json_safe(ws: WebSocket, data: dict):
    try:
        await ws.send_json(data)
    except Exception as e:
        logger.warning(f"Failed to send WS message: {e}")


def broadcast_to_team(team_id: int, message: dict, exclude_user_id: int = None):
    sockets = list(_get_team_sockets(team_id))
    if not sockets:
        return

    async def _do_broadcast():
        tasks = []
        for uid, ws in sockets:
            if exclude_user_id is not None and uid == exclude_user_id:
                continue
            tasks.append(_send_json_safe(ws, message))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_do_broadcast())
    except RuntimeError:
        asyncio.run(_do_broadcast())


@router.websocket("/{team_id}/ws")
async def team_websocket_endpoint(websocket: WebSocket, team_id: int, user_id: int):
    # 1. Validate team membership
    db = SessionLocal()
    try:
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            await websocket.close(code=4403, reason="Team not found")
            return
        member = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
            .first()
        )
        if not member:
            await websocket.close(code=4403, reason="Forbidden: Not a team member")
            return
    finally:
        db.close()

    await websocket.accept()

    # 2. Add to registry
    if team_id not in _team_connections:
        _team_connections[team_id] = set()
    _team_connections[team_id].add((user_id, websocket))

    # Broadcast member_online to team
    broadcast_to_team(
        team_id=team_id,
        message={"type": "member_online", "user_id": user_id},
        exclude_user_id=user_id,
    )

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if not msg_type:
                continue

            # Code sync / update per filename
            if msg_type in ("code-update", "code_sync", "code_diff", "cursor_move", "prompt_typing", "file_switch"):
                if msg_type in ("code-update", "code_sync") and data.get("code") is not None:
                    filename = data.get("filename")
                    code = data.get("code")
                    try:
                        db_ws = SessionLocal()
                        session = db_ws.query(ChallengeSession).filter(
                            ChallengeSession.team_id == team_id,
                            ChallengeSession.submitted_at.is_(None)
                        ).first()
                        if session:
                            if filename:
                                try:
                                    files_dict = json.loads(session.current_code or "{}")
                                    if not isinstance(files_dict, dict):
                                        files_dict = {}
                                except Exception:
                                    files_dict = {}
                                files_dict[filename] = code
                                session.current_code = json.dumps(files_dict)
                            else:
                                session.current_code = code
                            db_ws.commit()
                        db_ws.close()
                    except Exception as e:
                        logger.warning(f"Failed to persist live WS code for team {team_id}: {e}")

                broadcast_to_team(team_id=team_id, message=data, exclude_user_id=user_id)


            # Voice signaling (targeted)
            elif msg_type in ("voice-offer", "voice-answer", "voice-ice"):
                target_user_id = data.get("target_user_id")
                if target_user_id:
                    # Relay to specific target connections
                    target_sockets = [
                        ws for uid, ws in _get_team_sockets(team_id) if uid == target_user_id
                    ]
                    for target_ws in target_sockets:
                        await _send_json_safe(target_ws, data)

            # Mute state
            elif msg_type in ("mute-state", "mute_state"):
                broadcast_to_team(team_id=team_id, message=data, exclude_user_id=user_id)

            # Chat message relay
            elif msg_type == "chat_message":
                broadcast_to_team(team_id=team_id, message=data, exclude_user_id=user_id)

            # Member joined / team started relays
            elif msg_type in ("member_joined", "team_started"):
                broadcast_to_team(team_id=team_id, message=data, exclude_user_id=user_id)

            else:
                logger.warning(f"Unknown WS message type: {msg_type} from user {user_id}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket error for user {user_id} in team {team_id}: {e}")
    finally:
        if team_id in _team_connections:
            _team_connections[team_id].discard((user_id, websocket))
            if not _team_connections[team_id]:
                del _team_connections[team_id]

        broadcast_to_team(
            team_id=team_id,
            message={"type": "cursor_move", "user_id": user_id, "selection_start": None, "selection_end": None},
            exclude_user_id=user_id,
        )
        broadcast_to_team(
            team_id=team_id,
            message={"type": "prompt_typing", "user_id": user_id, "draft_text": ""},
            exclude_user_id=user_id,
        )
        broadcast_to_team(
            team_id=team_id,
            message={"type": "member_offline", "user_id": user_id},
            exclude_user_id=user_id,
        )
