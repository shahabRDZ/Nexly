import json
import uuid
import logging

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.database import async_session
from app.models.message import MessageStatus
from app.models.group import GroupMember
from app.services.auth_service import decode_access_token
from app.services.message_service import save_message, update_message_status
from app.services.presence_service import set_online, set_offline
from app.websocket.manager import manager

logger = logging.getLogger(__name__)


async def authenticate_ws(ws: WebSocket) -> uuid.UUID | None:
    token = ws.query_params.get("token")
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    return uuid.UUID(payload["sub"])


async def websocket_endpoint(ws: WebSocket):
    user_id = await authenticate_ws(ws)
    if not user_id:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(user_id, ws)

    async with async_session() as db:
        await set_online(db, user_id)
    await manager.broadcast_presence(user_id, is_online=True)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"event": "error", "data": {"detail": "Invalid JSON"}}))
                continue

            event = data.get("event")
            payload = data.get("data", {})

            if event == "message":
                await _handle_message(user_id, payload)
            elif event == "group_message":
                await _handle_group_message(user_id, payload)
            elif event == "typing":
                await _handle_typing(user_id, payload)
            elif event == "group_typing":
                await _handle_group_typing(user_id, payload)
            elif event == "seen":
                await _handle_seen(user_id, payload)
            elif event == "ping":
                await ws.send_text(json.dumps({"event": "pong", "data": {}}))
            # WebRTC signaling via WS
            elif event in ("webrtc_offer", "webrtc_answer", "webrtc_ice"):
                await _handle_webrtc(user_id, event, payload)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("WebSocket error for user %s: %s", user_id, e)
    finally:
        manager.disconnect(user_id, ws)
        async with async_session() as db:
            await set_offline(db, user_id)
        await manager.broadcast_presence(user_id, is_online=False)


async def _handle_message(sender_id: uuid.UUID, payload: dict):
    receiver_id = uuid.UUID(payload["receiver_id"])
    content = payload.get("content")
    message_type = payload.get("message_type", "text")
    reply_to_id = uuid.UUID(payload["reply_to_id"]) if payload.get("reply_to_id") else None

    async with async_session() as db:
        msg = await save_message(
            db, sender_id, receiver_id=receiver_id, content=content,
            message_type=message_type, reply_to_id=reply_to_id,
        )

    msg_data = _msg_to_dict(msg)

    delivered = await manager.send_to_user(receiver_id, "new_message", msg_data)
    if delivered:
        async with async_session() as db:
            await update_message_status(db, [msg.id], MessageStatus.DELIVERED, receiver_id)
        msg_data["status"] = "delivered"

    await manager.send_to_user(sender_id, "message_sent", msg_data)


async def _handle_group_message(sender_id: uuid.UUID, payload: dict):
    group_id = uuid.UUID(payload["group_id"])
    content = payload.get("content")
    message_type = payload.get("message_type", "text")
    reply_to_id = uuid.UUID(payload["reply_to_id"]) if payload.get("reply_to_id") else None

    async with async_session() as db:
        msg = await save_message(
            db, sender_id, group_id=group_id, content=content,
            message_type=message_type, reply_to_id=reply_to_id,
        )
        # Get all group members
        result = await db.execute(
            select(GroupMember.user_id).where(GroupMember.group_id == group_id)
        )
        member_ids = [row[0] for row in result.all()]

    msg_data = _msg_to_dict(msg)

    # Send to all group members except sender
    for mid in member_ids:
        if mid != sender_id:
            await manager.send_to_user(mid, "group_message", msg_data)

    await manager.send_to_user(sender_id, "message_sent", msg_data)


async def _handle_typing(sender_id: uuid.UUID, payload: dict):
    receiver_id = uuid.UUID(payload["receiver_id"])
    await manager.send_to_user(
        receiver_id, "typing", {"user_id": str(sender_id), "is_typing": payload.get("is_typing", True)}
    )


async def _handle_group_typing(sender_id: uuid.UUID, payload: dict):
    group_id = uuid.UUID(payload["group_id"])
    async with async_session() as db:
        result = await db.execute(
            select(GroupMember.user_id).where(GroupMember.group_id == group_id)
        )
        member_ids = [row[0] for row in result.all()]

    for mid in member_ids:
        if mid != sender_id:
            await manager.send_to_user(mid, "group_typing", {
                "group_id": str(group_id),
                "user_id": str(sender_id),
                "is_typing": payload.get("is_typing", True),
            })


async def _handle_seen(user_id: uuid.UUID, payload: dict):
    message_ids = [uuid.UUID(mid) for mid in payload.get("message_ids", [])]
    sender_id = uuid.UUID(payload["sender_id"])

    async with async_session() as db:
        await update_message_status(db, message_ids, MessageStatus.SEEN, user_id)

    await manager.send_to_user(
        sender_id, "messages_seen",
        {"message_ids": [str(mid) for mid in message_ids], "seen_by": str(user_id)},
    )


async def _handle_webrtc(sender_id: uuid.UUID, event: str, payload: dict):
    """Forward WebRTC signaling to the other party."""
    target_id = uuid.UUID(payload["target_id"])
    await manager.send_to_user(target_id, event, {
        **payload,
        "from_user_id": str(sender_id),
    })


def _msg_to_dict(msg) -> dict:
    return {
        "id": str(msg.id),
        "sender_id": str(msg.sender_id),
        "receiver_id": str(msg.receiver_id) if msg.receiver_id else None,
        "group_id": str(msg.group_id) if msg.group_id else None,
        "channel_id": str(msg.channel_id) if msg.channel_id else None,
        "content": msg.content,
        "message_type": msg.message_type.value if hasattr(msg.message_type, 'value') else msg.message_type,
        "media_url": msg.media_url,
        "status": msg.status.value if hasattr(msg.status, 'value') else msg.status,
        "reply_to_id": str(msg.reply_to_id) if msg.reply_to_id else None,
        "is_forwarded": msg.is_forwarded,
        "is_pinned": msg.is_pinned,
        "created_at": msg.created_at.isoformat(),
    }
