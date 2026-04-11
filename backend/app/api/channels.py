import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.channel import Channel, ChannelSubscriber
from app.models.message import Message
from app.models.user import User
from app.services.message_service import save_message

router = APIRouter(prefix="/channels", tags=["channels"])


class ChannelCreate(BaseModel):
    name: str
    username: str | None = None
    description: str = ""
    is_public: bool = True


class ChannelOut(BaseModel):
    id: uuid.UUID
    name: str
    username: str | None
    description: str
    avatar_url: str | None
    is_public: bool
    subscriber_count: int
    creator_id: uuid.UUID
    is_admin: bool = False
    model_config = {"from_attributes": True}


class ChannelPost(BaseModel):
    content: str | None = None
    message_type: str = "text"


@router.post("/", response_model=ChannelOut)
async def create_channel(
    body: ChannelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.username:
        existing = await db.execute(select(Channel).where(Channel.username == body.username))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username taken")

    channel = Channel(
        name=body.name, username=body.username, description=body.description,
        is_public=body.is_public, creator_id=current_user.id, subscriber_count=1,
    )
    db.add(channel)
    await db.flush()
    db.add(ChannelSubscriber(channel_id=channel.id, user_id=current_user.id, is_admin=True))
    await db.commit()
    await db.refresh(channel)
    return ChannelOut(
        id=channel.id, name=channel.name, username=channel.username,
        description=channel.description, avatar_url=channel.avatar_url,
        is_public=channel.is_public, subscriber_count=1,
        creator_id=channel.creator_id, is_admin=True,
    )


@router.get("/", response_model=list[ChannelOut])
async def list_my_channels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Channel, ChannelSubscriber.is_admin)
        .join(ChannelSubscriber, ChannelSubscriber.channel_id == Channel.id)
        .where(ChannelSubscriber.user_id == current_user.id)
    )
    return [
        ChannelOut(
            id=c.id, name=c.name, username=c.username, description=c.description,
            avatar_url=c.avatar_url, is_public=c.is_public,
            subscriber_count=c.subscriber_count, creator_id=c.creator_id, is_admin=is_admin,
        )
        for c, is_admin in result.all()
    ]


@router.get("/explore", response_model=list[ChannelOut])
async def explore_channels(
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Channel).where(Channel.is_public == True)
    if q:
        query = query.where(Channel.name.ilike(f"%{q}%"))
    query = query.order_by(Channel.subscriber_count.desc()).limit(50)
    result = await db.execute(query)
    return [
        ChannelOut(
            id=c.id, name=c.name, username=c.username, description=c.description,
            avatar_url=c.avatar_url, is_public=c.is_public,
            subscriber_count=c.subscriber_count, creator_id=c.creator_id,
        )
        for c in result.scalars().all()
    ]


@router.post("/{channel_id}/subscribe")
async def subscribe(
    channel_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    channel = await db.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    existing = await db.execute(
        select(ChannelSubscriber).where(
            ChannelSubscriber.channel_id == channel_id, ChannelSubscriber.user_id == current_user.id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already subscribed")
    db.add(ChannelSubscriber(channel_id=channel_id, user_id=current_user.id))
    channel.subscriber_count += 1
    await db.commit()
    return {"detail": "Subscribed"}


@router.delete("/{channel_id}/subscribe")
async def unsubscribe(
    channel_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChannelSubscriber).where(
            ChannelSubscriber.channel_id == channel_id, ChannelSubscriber.user_id == current_user.id
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Not subscribed")
    if sub.is_admin:
        raise HTTPException(status_code=400, detail="Admins cannot unsubscribe")
    await db.delete(sub)
    channel = await db.get(Channel, channel_id)
    channel.subscriber_count = max(0, channel.subscriber_count - 1)
    await db.commit()
    return {"detail": "Unsubscribed"}


@router.post("/{channel_id}/post")
async def create_post(
    channel_id: uuid.UUID,
    body: ChannelPost,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChannelSubscriber).where(
            ChannelSubscriber.channel_id == channel_id,
            ChannelSubscriber.user_id == current_user.id,
            ChannelSubscriber.is_admin == True,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Only admins can post")

    msg = await save_message(
        db, sender_id=current_user.id, content=body.content,
        message_type=body.message_type, channel_id=channel_id,
    )
    return msg


@router.get("/{channel_id}/posts")
async def get_posts(
    channel_id: uuid.UUID,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Message)
        .where(Message.channel_id == channel_id, Message.deleted_for_all == False)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))
