"""AI-powered features: Smart Reply, Chat Summary, Voice-to-Text, AI Bot."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.message import Message
from app.models.user import User
from app.services.ai_service import (
    generate_smart_replies,
    summarize_chat,
    transcribe_voice_url,
    ask_ai_bot,
)

router = APIRouter(prefix="/ai", tags=["ai"])


# ── Smart Reply ──

class SmartReplyRequest(BaseModel):
    conversation_user_id: uuid.UUID
    limit: int = 10


@router.post("/smart-reply")
async def get_smart_replies(
    body: SmartReplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate 3 smart reply suggestions based on recent conversation."""
    result = await db.execute(
        select(Message)
        .where(
            or_(
                and_(Message.sender_id == current_user.id, Message.receiver_id == body.conversation_user_id),
                and_(Message.sender_id == body.conversation_user_id, Message.receiver_id == current_user.id),
            ),
            Message.message_type == "text",
            Message.deleted_for_all == False,
        )
        .order_by(Message.created_at.desc())
        .limit(body.limit)
    )
    messages = list(reversed(result.scalars().all()))

    if not messages:
        return {"replies": ["Hi!", "How are you?", "👋"]}

    history = [
        {"role": "me" if m.sender_id == current_user.id else "them", "text": m.content or ""}
        for m in messages
    ]

    replies = await generate_smart_replies(history, current_user.preferred_language)
    return {"replies": replies}


# ── Chat Summary ──

class SummaryRequest(BaseModel):
    conversation_user_id: uuid.UUID | None = None
    group_id: uuid.UUID | None = None
    hours: int = 24


@router.post("/summary")
async def get_chat_summary(
    body: SummaryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Summarize unread or recent messages in a conversation."""
    since = datetime.now(timezone.utc) - timedelta(hours=body.hours)

    if body.conversation_user_id:
        result = await db.execute(
            select(Message)
            .where(
                or_(
                    and_(Message.sender_id == current_user.id, Message.receiver_id == body.conversation_user_id),
                    and_(Message.sender_id == body.conversation_user_id, Message.receiver_id == current_user.id),
                ),
                Message.created_at > since,
                Message.message_type == "text",
            )
            .order_by(Message.created_at.asc())
            .limit(100)
        )
    elif body.group_id:
        result = await db.execute(
            select(Message)
            .where(Message.group_id == body.group_id, Message.created_at > since, Message.message_type == "text")
            .order_by(Message.created_at.asc())
            .limit(100)
        )
    else:
        raise HTTPException(status_code=400, detail="Provide conversation_user_id or group_id")

    messages = result.scalars().all()
    if not messages:
        return {"summary": "No messages in this period.", "message_count": 0}

    texts = [m.content for m in messages if m.content]
    summary = await summarize_chat(texts, current_user.preferred_language)
    return {"summary": summary, "message_count": len(messages)}


# ── Voice-to-Text ──

class TranscribeRequest(BaseModel):
    message_id: uuid.UUID


@router.post("/transcribe")
async def transcribe_voice(
    body: TranscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Transcribe a voice message to text."""
    msg = await db.get(Message, body.message_id)
    if not msg or msg.message_type != "voice":
        raise HTTPException(status_code=400, detail="Not a voice message")

    # Return cached transcript if available
    if msg.voice_transcript:
        return {"transcript": msg.voice_transcript, "cached": True}

    if not msg.media_url:
        raise HTTPException(status_code=400, detail="No audio file")

    transcript = await transcribe_voice_url(msg.media_url, current_user.preferred_language)
    msg.voice_transcript = transcript
    await db.commit()
    return {"transcript": transcript, "cached": False}


# ── AI Chat Bot ──

class BotRequest(BaseModel):
    message: str


@router.post("/bot")
async def chat_with_bot(
    body: BotRequest,
    current_user: User = Depends(get_current_user),
):
    """Chat with Nexly AI assistant."""
    response = await ask_ai_bot(body.message, current_user.preferred_language, current_user.name)
    return {"response": response}
