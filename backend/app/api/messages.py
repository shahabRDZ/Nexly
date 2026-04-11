import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.message import Message, MessageDeletion, ReadReceipt
from app.models.user import User
from app.schemas.message import MessageOut, MessageStatusUpdate, ConversationPreview, UserPreview
from app.services.message_service import (
    get_conversation,
    update_message_status,
    get_conversations_list,
    save_message,
)

router = APIRouter(prefix="/messages", tags=["messages"])

ALLOWED_IMAGE = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO = {"video/mp4", "video/webm", "video/quicktime"}
ALLOWED_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.get("/conversations", response_model=list[ConversationPreview])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    convos = await get_conversations_list(db, current_user.id)
    return [
        ConversationPreview(
            user=UserPreview.model_validate(c["partner"]),
            last_message=MessageOut.model_validate(c["last_message"]) if c["last_message"] else None,
            unread_count=c["unread_count"],
        )
        for c in convos
    ]


@router.get("/{other_user_id}", response_model=list[MessageOut])
async def get_messages(
    other_user_id: uuid.UUID,
    limit: int = 50,
    before: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages = await get_conversation(db, current_user.id, other_user_id, limit, before)
    return messages


@router.patch("/status")
async def mark_messages(
    body: MessageStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await update_message_status(db, body.message_ids, body.status, current_user.id)
    return {"updated": count}


# ── Media Upload (Image / Video / File) ──


async def _save_upload(file: UploadFile, subdir: str) -> tuple[str, int, str]:
    """Save uploaded file and return (url, size, original_name)."""
    upload_dir = os.path.join(settings.media_dir, subdir)
    os.makedirs(upload_dir, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "bin"
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(upload_dir, filename)
    content = await file.read()
    if len(content) > ALLOWED_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(content)
    return f"/media/{subdir}/{filename}", len(content), file.filename or filename


@router.post("/media/{receiver_id}", response_model=MessageOut)
async def send_media(
    receiver_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send image, video, or file message."""
    ct = file.content_type or ""
    if ct in ALLOWED_IMAGE:
        msg_type, subdir = "image", "images"
    elif ct in ALLOWED_VIDEO:
        msg_type, subdir = "video", "videos"
    else:
        msg_type, subdir = "file", "files"

    url, size, name = await _save_upload(file, subdir)
    msg = await save_message(
        db,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=name,
        message_type=msg_type,
        media_url=url,
        media_size=size,
        media_name=name,
    )
    return msg


@router.post("/voice/{receiver_id}", response_model=MessageOut)
async def send_voice_message(
    receiver_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    url, size, name = await _save_upload(file, "voice")
    msg = await save_message(
        db,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=None,
        message_type="voice",
        media_url=url,
    )
    return msg


# ── Reply ──


@router.post("/reply/{message_id}", response_model=MessageOut)
async def reply_to_message(
    message_id: uuid.UUID,
    receiver_id: uuid.UUID,
    content: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    original = await db.get(Message, message_id)
    if not original:
        raise HTTPException(status_code=404, detail="Original message not found")

    msg = await save_message(
        db,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        reply_to_id=message_id,
    )
    return msg


# ── Forward ──


@router.post("/forward/{message_id}", response_model=MessageOut)
async def forward_message(
    message_id: uuid.UUID,
    receiver_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    original = await db.get(Message, message_id)
    if not original:
        raise HTTPException(status_code=404, detail="Message not found")

    msg = await save_message(
        db,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=original.content,
        message_type=original.message_type.value,
        media_url=original.media_url,
        is_forwarded=True,
        forwarded_from_id=original.id,
    )
    return msg


# ── Delete ──


@router.delete("/{message_id}")
async def delete_message(
    message_id: uuid.UUID,
    for_all: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await db.get(Message, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if for_all:
        if msg.sender_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only sender can delete for all")
        msg.deleted_for_all = True
        msg.content = None
        msg.media_url = None
        await db.commit()
        return {"detail": "Deleted for everyone"}
    else:
        db.add(MessageDeletion(message_id=message_id, user_id=current_user.id))
        await db.commit()
        return {"detail": "Deleted for you"}


# ── Pin ──


@router.post("/{message_id}/pin")
async def pin_message(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await db.get(Message, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    from datetime import datetime, timezone
    msg.is_pinned = True
    msg.pinned_at = datetime.now(timezone.utc)
    await db.commit()
    return {"detail": "Message pinned"}


@router.delete("/{message_id}/pin")
async def unpin_message(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await db.get(Message, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.is_pinned = False
    msg.pinned_at = None
    await db.commit()
    return {"detail": "Message unpinned"}


# ── Read Receipts ──


@router.get("/{message_id}/receipts")
async def get_read_receipts(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ReadReceipt, User)
        .join(User, ReadReceipt.user_id == User.id)
        .where(ReadReceipt.message_id == message_id)
    )
    receipts = [
        {"user_id": str(r.user_id), "name": u.name, "avatar_url": u.avatar_url, "read_at": r.read_at.isoformat()}
        for r, u in result.all()
    ]
    return receipts
