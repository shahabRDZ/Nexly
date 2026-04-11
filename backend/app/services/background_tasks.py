"""
Background task runner — handles:
  C-3: Deleting expired disappearing messages
  C-4: Sending scheduled messages

Runs as an asyncio task inside the FastAPI app lifecycle.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, delete, and_

from app.database import async_session
from app.models.message import Message
from app.models.schedule import ScheduledMessage
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None


async def _cleanup_loop():
    """Run cleanup every 30 seconds."""
    while True:
        try:
            await _delete_expired_messages()
            await _send_scheduled_messages()
        except Exception as e:
            logger.error("Background task error: %s", e)
        await asyncio.sleep(30)


async def _delete_expired_messages():
    """C-3 FIX: Delete messages past their expires_at."""
    async with async_session() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Message).where(
                Message.expires_at != None,
                Message.expires_at <= now,
                Message.deleted_for_all == False,
            ).limit(100)
        )
        expired = result.scalars().all()
        if not expired:
            return

        for msg in expired:
            msg.deleted_for_all = True
            msg.content = None
            msg.media_url = None
            # Notify participants
            targets = set()
            if msg.sender_id:
                targets.add(msg.sender_id)
            if msg.receiver_id:
                targets.add(msg.receiver_id)
            for uid in targets:
                await manager.send_to_user(uid, "message_expired", {"message_id": str(msg.id)})

        await db.commit()
        logger.info("Cleaned up %d expired messages", len(expired))


async def _send_scheduled_messages():
    """C-4 FIX: Send scheduled messages that are due."""
    async with async_session() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ScheduledMessage).where(
                ScheduledMessage.sent == False,
                ScheduledMessage.send_at <= now,
            ).limit(50)
        )
        due = result.scalars().all()
        if not due:
            return

        from app.services.message_service import save_message

        for sm in due:
            try:
                msg = await save_message(
                    db,
                    sender_id=sm.sender_id,
                    receiver_id=sm.receiver_id,
                    group_id=sm.group_id,
                    content=sm.content,
                    message_type="text",
                )
                sm.sent = True

                # Deliver via WebSocket
                msg_data = {
                    "id": str(msg.id),
                    "sender_id": str(msg.sender_id),
                    "receiver_id": str(msg.receiver_id) if msg.receiver_id else None,
                    "group_id": str(msg.group_id) if msg.group_id else None,
                    "content": msg.content,
                    "message_type": "text",
                    "status": "sent",
                    "created_at": msg.created_at.isoformat(),
                }

                if sm.receiver_id:
                    await manager.send_to_user(sm.receiver_id, "new_message", msg_data)
                    await manager.send_to_user(sm.sender_id, "message_sent", msg_data)

            except Exception as e:
                logger.error("Failed to send scheduled message %s: %s", sm.id, e)

        await db.commit()
        if due:
            logger.info("Sent %d scheduled messages", len([m for m in due if m.sent]))


def start_background_tasks():
    """Start background task loop."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_cleanup_loop())
        logger.info("Background tasks started")


def stop_background_tasks():
    global _task
    if _task and not _task.done():
        _task.cancel()
        logger.info("Background tasks stopped")
