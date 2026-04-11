"""Enhanced message features: edit, search, disappearing, location, stickers/GIF."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.message import Message
from app.models.user import User
from app.services.message_service import save_message
from app.websocket.manager import manager

router = APIRouter(prefix="/messages", tags=["enhanced-messages"])


# ── Edit Message ──

class EditRequest(BaseModel):
    content: str


@router.patch("/{message_id}/edit")
async def edit_message(
    message_id: uuid.UUID,
    body: EditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await db.get(Message, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only sender can edit")

    # Allow edit within 48 hours
    if (datetime.now(timezone.utc) - msg.created_at.replace(tzinfo=timezone.utc)).total_seconds() > 172800:
        raise HTTPException(status_code=400, detail="Cannot edit messages older than 48 hours")

    msg.content = body.content
    msg.edited_at = datetime.now(timezone.utc)
    await db.commit()

    # Notify the other user
    target_id = msg.receiver_id
    if target_id:
        await manager.send_to_user(target_id, "message_edited", {
            "message_id": str(message_id), "content": body.content,
            "edited_at": msg.edited_at.isoformat(),
        })

    return {"detail": "Message edited", "edited_at": msg.edited_at.isoformat()}


# ── Search Messages ──

@router.get("/search/{query}")
async def search_messages(
    query: str,
    other_user_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search in messages."""
    q = select(Message).where(
        Message.content.ilike(f"%{query}%"),
        Message.deleted_for_all == False,
        Message.message_type == "text",
    )

    if other_user_id:
        q = q.where(or_(
            and_(Message.sender_id == current_user.id, Message.receiver_id == other_user_id),
            and_(Message.sender_id == other_user_id, Message.receiver_id == current_user.id),
        ))
    elif group_id:
        q = q.where(Message.group_id == group_id)
    else:
        q = q.where(or_(Message.sender_id == current_user.id, Message.receiver_id == current_user.id))

    q = q.order_by(Message.created_at.desc()).limit(limit)
    result = await db.execute(q)
    messages = result.scalars().all()

    return [
        {
            "id": str(m.id), "sender_id": str(m.sender_id),
            "receiver_id": str(m.receiver_id) if m.receiver_id else None,
            "group_id": str(m.group_id) if m.group_id else None,
            "content": m.content, "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


# ── Disappearing Messages ──

class DisappearingRequest(BaseModel):
    receiver_id: uuid.UUID
    content: str
    expire_seconds: int = 30  # 30s, 3600=1h, 86400=24h


@router.post("/disappearing")
async def send_disappearing_message(
    body: DisappearingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=body.expire_seconds)
    msg = await save_message(
        db, sender_id=current_user.id, receiver_id=body.receiver_id,
        content=body.content, message_type="text",
    )
    msg.expires_at = expires_at
    await db.commit()
    await db.refresh(msg)

    await manager.send_to_user(body.receiver_id, "new_message", {
        "id": str(msg.id), "sender_id": str(msg.sender_id),
        "receiver_id": str(msg.receiver_id), "content": msg.content,
        "message_type": "text", "status": "sent",
        "expires_at": expires_at.isoformat(),
        "created_at": msg.created_at.isoformat(),
    })

    return {"id": str(msg.id), "expires_at": expires_at.isoformat()}


# ── View Once ──

class ViewOnceRequest(BaseModel):
    receiver_id: uuid.UUID


@router.post("/view-once/{message_id}/open")
async def open_view_once(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await db.get(Message, message_id)
    if not msg or not msg.view_once:
        raise HTTPException(status_code=404, detail="Not a view-once message")
    if msg.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the receiver")
    if msg.view_once_opened:
        raise HTTPException(status_code=400, detail="Already opened")

    msg.view_once_opened = True
    await db.commit()

    # Notify sender
    await manager.send_to_user(msg.sender_id, "view_once_opened", {
        "message_id": str(message_id), "opened_by": str(current_user.id),
    })
    return {"media_url": msg.media_url, "message_type": msg.message_type.value}


# ── Send Location ──

class LocationRequest(BaseModel):
    receiver_id: uuid.UUID
    latitude: float
    longitude: float
    location_name: str | None = None


@router.post("/location")
async def send_location(
    body: LocationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await save_message(
        db, sender_id=current_user.id, receiver_id=body.receiver_id,
        content=body.location_name or f"{body.latitude},{body.longitude}",
        message_type="location",
    )
    msg.latitude = body.latitude
    msg.longitude = body.longitude
    msg.location_name = body.location_name
    await db.commit()
    await db.refresh(msg)

    await manager.send_to_user(body.receiver_id, "new_message", {
        "id": str(msg.id), "sender_id": str(msg.sender_id),
        "receiver_id": str(msg.receiver_id), "content": msg.content,
        "message_type": "location", "status": "sent",
        "latitude": body.latitude, "longitude": body.longitude,
        "location_name": body.location_name,
        "created_at": msg.created_at.isoformat(),
    })
    return msg


# ── Send Sticker/GIF ──

class StickerRequest(BaseModel):
    receiver_id: uuid.UUID
    url: str
    type: str = "sticker"  # sticker or gif


@router.post("/sticker")
async def send_sticker(
    body: StickerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg_type = "gif" if body.type == "gif" else "sticker"
    msg = await save_message(
        db, sender_id=current_user.id, receiver_id=body.receiver_id,
        message_type=msg_type, media_url=body.url,
    )
    msg.sticker_url = body.url
    await db.commit()

    await manager.send_to_user(body.receiver_id, "new_message", {
        "id": str(msg.id), "sender_id": str(msg.sender_id),
        "receiver_id": str(msg.receiver_id),
        "message_type": msg_type, "media_url": body.url,
        "sticker_url": body.url, "status": "sent",
        "created_at": msg.created_at.isoformat(),
    })
    return msg
