"""Saved Messages — the user's private scratchpad (self-chat).

Stored as Message rows with sender_id == receiver_id == current_user.id.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.message import Message, MessageDeletion, MessageStatus
from app.models.user import User
from app.schemas.message import MessageOut
from app.services.message_service import save_message
from app.api.messages import _save_upload

router = APIRouter(prefix="/saved", tags=["saved-messages"])


class SavedText(BaseModel):
    content: str


@router.get("/", response_model=list[MessageOut])
async def list_saved(
    limit: int = 50,
    before: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.id

    # Exclude per-user soft-deletions
    del_q = select(MessageDeletion.message_id).where(MessageDeletion.user_id == uid)
    deleted = {row[0] for row in (await db.execute(del_q)).all()}

    q = select(Message).where(
        Message.sender_id == uid,
        Message.receiver_id == uid,
        Message.deleted_for_all == False,
    )
    if before:
        sub = select(Message.created_at).where(Message.id == before).scalar_subquery()
        q = q.where(Message.created_at < sub)
    q = q.order_by(Message.created_at.desc()).limit(limit)

    result = await db.execute(q)
    msgs = [m for m in result.scalars().all() if m.id not in deleted]
    return list(reversed(msgs))


@router.post("/text", response_model=MessageOut)
async def save_text(
    body: SavedText,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Empty content")
    msg = await save_message(
        db,
        sender_id=current_user.id,
        receiver_id=current_user.id,
        content=content[:5000],
        message_type="text",
    )
    # Self-chat is seen by definition
    msg.status = MessageStatus.SEEN
    await db.commit()
    await db.refresh(msg)
    return msg


@router.post("/media", response_model=MessageOut)
async def save_media(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ct = file.content_type or ""
    if ct.startswith("image/"):
        msg_type, subdir = "image", "images"
    elif ct.startswith("video/"):
        msg_type, subdir = "video", "videos"
    else:
        msg_type, subdir = "file", "files"

    url, size, name = await _save_upload(file, subdir)
    msg = await save_message(
        db,
        sender_id=current_user.id,
        receiver_id=current_user.id,
        content=name,
        message_type=msg_type,
        media_url=url,
        media_size=size,
        media_name=name,
    )
    msg.status = MessageStatus.SEEN
    await db.commit()
    await db.refresh(msg)
    return msg


@router.post("/forward/{message_id}", response_model=MessageOut)
async def forward_to_saved(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save an existing message into the user's Saved Messages."""
    original = await db.get(Message, message_id)
    if not original:
        raise HTTPException(status_code=404, detail="Message not found")
    # Must be a participant in the source conversation (or group/channel access)
    participant = (
        current_user.id in (original.sender_id, original.receiver_id)
        or original.group_id is not None
        or original.channel_id is not None
    )
    if not participant:
        raise HTTPException(status_code=403, detail="Cannot access that message")

    msg = await save_message(
        db,
        sender_id=current_user.id,
        receiver_id=current_user.id,
        content=original.content,
        message_type=original.message_type.value if hasattr(original.message_type, "value") else str(original.message_type),
        media_url=original.media_url,
        media_size=original.media_size,
        media_name=original.media_name,
        is_forwarded=True,
        forwarded_from_id=original.id,
    )
    msg.status = MessageStatus.SEEN
    await db.commit()
    await db.refresh(msg)
    return msg
