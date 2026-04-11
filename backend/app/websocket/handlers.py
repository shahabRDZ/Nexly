import json
import uuid
import logging

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.message import Message, MessageStatus
from app.models.group import GroupMember
from app.models.user import User
from app.services.auth_service import decode_access_token
from app.services.message_service import save_message, update_message_status
from app.services.presence_service import set_online, set_offline
from app.services.translation_service import translate_for_user, detect_language
from app.websocket.manager import manager

logger = logging.getLogger(__name__)


async def _get_user_lang(user_id: uuid.UUID) -> str:
    """Fetch user's preferred language from DB."""
    async with async_session() as db:
        result = await db.execute(select(User.preferred_language).where(User.id == user_id))
        lang = result.scalar_one_or_none()
        return lang or "en"


async def _get_recent_context(sender_id: uuid.UUID, receiver_id: uuid.UUID, limit: int = 3) -> list[str]:
    """Get recent message texts for translation context."""
    try:
        async with async_session() as db:
            from sqlalchemy import and_, or_
            result = await db.execute(
                select(Message.content)
                .where(
                    or_(
                        and_(Message.sender_id == sender_id, Message.receiver_id == receiver_id),
                        and_(Message.sender_id == receiver_id, Message.receiver_id == sender_id),
                    ),
                    Message.message_type == "text",
                    Message.content != None,
                )
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            texts = [r[0] for r in result.all() if r[0]]
            return list(reversed(texts))
    except Exception:
        return []


async def _translate_content(
    content: str | None,
    sender_id: uuid.UUID,
    receiver_id: uuid.UUID,
    sender_lang: str | None = None,
    context: list[str] | None = None,
) -> tuple[str | None, str | None, str | None, bool]:
    """
    Smart translation with auto-detection and context.
    Returns: (translated_content, original_content, detected_source_lang, was_translated)
    """
    if not content or not settings.translation_enabled:
        return content, None, None, False

    if sender_lang is None:
        sender_lang = await _get_user_lang(sender_id)
    receiver_lang = await _get_user_lang(receiver_id)

    # CRITICAL: Don't skip based on preferred_language alone.
    # Auto-detect ACTUAL language and translate if it differs from receiver's lang.
    try:
        from app.services.translation_service import detect_language
        actual_lang = await detect_language(content)

        # If text is already in receiver's language, skip
        if actual_lang == receiver_lang:
            return content, None, actual_lang, False

        # Get conversation context for fluent translation
        if context is None:
            context = await _get_recent_context(sender_id, receiver_id)

        result = await translate_for_user(content, actual_lang, receiver_lang, context)

        if result.confidence > 0 and result.translated_text != content:
            return result.translated_text, content, actual_lang, True
        return content, None, actual_lang, False
    except Exception as e:
        logger.error("Translation error: %s", e)
        return content, None, sender_lang, False


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


def _safe_uuid(val) -> uuid.UUID | None:
    """C-4 FIX: Safe UUID parsing — returns None instead of crashing."""
    if not val:
        return None
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError):
        return None


async def _handle_message(sender_id: uuid.UUID, payload: dict):
    receiver_id = _safe_uuid(payload.get("receiver_id"))
    if not receiver_id:
        return  # Invalid payload, ignore silently
    content = payload.get("content", "")[:5000]  # M-6: limit content length
    message_type = payload.get("message_type", "text")
    reply_to_id = _safe_uuid(payload.get("reply_to_id"))

    # ── Smart Translation Layer ──
    # Auto-detect language from text + use conversation context for fluency
    sender_lang = await _get_user_lang(sender_id)
    context = await _get_recent_context(sender_id, receiver_id) if content else None
    translated_content, original_content, source_lang, was_translated = \
        await _translate_content(content, sender_id, receiver_id, sender_lang, context)

    # Save the original message (in sender's language) to DB
    async with async_session() as db:
        msg = await save_message(
            db, sender_id, receiver_id=receiver_id,
            content=content,  # Store original in content
            original_content=content if was_translated else None,
            source_language=source_lang,
            translated=was_translated,
            message_type=message_type, reply_to_id=reply_to_id,
        )

    # Build base message data
    base_data = _msg_to_dict(msg)

    # Send TRANSLATED version to receiver
    receiver_data = {**base_data}
    if was_translated:
        receiver_data["content"] = translated_content
        receiver_data["original_content"] = content
        receiver_data["source_language"] = source_lang
        receiver_data["translated"] = True

    delivered = await manager.send_to_user(receiver_id, "new_message", receiver_data)

    if delivered:
        async with async_session() as db:
            await update_message_status(db, [msg.id], MessageStatus.DELIVERED, receiver_id)
        base_data["status"] = "delivered"

    # Send ORIGINAL (untranslated) to sender as confirmation
    sender_data = {**base_data, "translated": False}
    await manager.send_to_user(sender_id, "message_sent", sender_data)


async def _handle_group_message(sender_id: uuid.UUID, payload: dict):
    group_id = _safe_uuid(payload.get("group_id"))
    if not group_id:
        return
    content = payload.get("content", "")[:5000]
    message_type = payload.get("message_type", "text")
    reply_to_id = _safe_uuid(payload.get("reply_to_id"))

    sender_lang = await _get_user_lang(sender_id)

    async with async_session() as db:
        msg = await save_message(
            db, sender_id, group_id=group_id, content=content,
            original_content=content,
            source_language=sender_lang,
            message_type=message_type, reply_to_id=reply_to_id,
        )
        result = await db.execute(
            select(GroupMember.user_id).where(GroupMember.group_id == group_id)
        )
        member_ids = [row[0] for row in result.all()]

    base_data = _msg_to_dict(msg)

    # ── Translate for EACH group member individually ──
    for mid in member_ids:
        if mid == sender_id:
            continue

        member_data = {**base_data}
        if content and settings.translation_enabled:
            translated_content, original, src, was_translated = \
                await _translate_content(content, sender_id, mid, sender_lang)
            if was_translated:
                member_data["content"] = translated_content
                member_data["original_content"] = content
                member_data["source_language"] = sender_lang
                member_data["translated"] = True

        await manager.send_to_user(mid, "group_message", member_data)

    # Original to sender
    await manager.send_to_user(sender_id, "message_sent", {**base_data, "translated": False})


async def _handle_typing(sender_id: uuid.UUID, payload: dict):
    receiver_id = _safe_uuid(payload.get("receiver_id"))
    if not receiver_id:
        return
    await manager.send_to_user(
        receiver_id, "typing", {"user_id": str(sender_id), "is_typing": payload.get("is_typing", True)}
    )


async def _handle_group_typing(sender_id: uuid.UUID, payload: dict):
    group_id = _safe_uuid(payload.get("group_id"))
    if not group_id:
        return
    async with async_session() as db:
        result = await db.execute(
            select(GroupMember.user_id).where(GroupMember.group_id == group_id)
        )
        member_ids = [row[0] for row in result.all()]

    for mid in member_ids:
        if mid != sender_id:
            await manager.send_to_user(mid, "group_typing", {
                "group_id": str(group_id), "user_id": str(sender_id),
                "is_typing": payload.get("is_typing", True),
            })


async def _handle_seen(user_id: uuid.UUID, payload: dict):
    message_ids = [u for mid in payload.get("message_ids", []) if (u := _safe_uuid(mid))]
    sender_id = _safe_uuid(payload.get("sender_id"))
    if not sender_id or not message_ids:
        return

    async with async_session() as db:
        await update_message_status(db, message_ids, MessageStatus.SEEN, user_id)

    await manager.send_to_user(
        sender_id, "messages_seen",
        {"message_ids": [str(mid) for mid in message_ids], "seen_by": str(user_id)},
    )


async def _handle_webrtc(sender_id: uuid.UUID, event: str, payload: dict):
    target_id = _safe_uuid(payload.get("target_id"))
    if not target_id:
        return
    await manager.send_to_user(target_id, event, {
        **payload, "from_user_id": str(sender_id),
    })


def _msg_to_dict(msg) -> dict:
    return {
        "id": str(msg.id),
        "sender_id": str(msg.sender_id),
        "receiver_id": str(msg.receiver_id) if msg.receiver_id else None,
        "group_id": str(msg.group_id) if msg.group_id else None,
        "channel_id": str(msg.channel_id) if msg.channel_id else None,
        "content": msg.content,
        "original_content": msg.original_content,
        "source_language": msg.source_language,
        "translated": msg.translated,
        "message_type": msg.message_type.value if hasattr(msg.message_type, 'value') else msg.message_type,
        "media_url": msg.media_url,
        "status": msg.status.value if hasattr(msg.status, 'value') else msg.status,
        "reply_to_id": str(msg.reply_to_id) if msg.reply_to_id else None,
        "is_forwarded": msg.is_forwarded,
        "is_pinned": msg.is_pinned,
        "created_at": msg.created_at.isoformat(),
    }
