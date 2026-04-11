import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.reaction import Reaction
from app.models.user import User
from app.websocket.manager import manager

router = APIRouter(prefix="/reactions", tags=["reactions"])

ALLOWED_EMOJIS = {"❤️", "👍", "😂", "😮", "😢", "🔥", "🎉", "💯", "🤔", "👎"}


class ReactRequest(BaseModel):
    message_id: uuid.UUID
    emoji: str


class ReactionOut(BaseModel):
    emoji: str
    count: int
    users: list[str]  # user IDs
    reacted_by_me: bool


@router.post("/")
async def add_reaction(
    body: ReactRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.emoji not in ALLOWED_EMOJIS:
        raise HTTPException(status_code=400, detail=f"Emoji not allowed. Use: {ALLOWED_EMOJIS}")

    existing = await db.execute(
        select(Reaction).where(
            Reaction.message_id == body.message_id,
            Reaction.user_id == current_user.id,
            Reaction.emoji == body.emoji,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already reacted")

    db.add(Reaction(message_id=body.message_id, user_id=current_user.id, emoji=body.emoji))
    await db.commit()

    # Notify via WebSocket
    await _broadcast_reactions(db, body.message_id)
    return {"detail": "Reaction added"}


@router.delete("/{message_id}/{emoji}")
async def remove_reaction(
    message_id: uuid.UUID,
    emoji: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Reaction).where(
            Reaction.message_id == message_id,
            Reaction.user_id == current_user.id,
            Reaction.emoji == emoji,
        )
    )
    reaction = result.scalar_one_or_none()
    if not reaction:
        raise HTTPException(status_code=404, detail="Reaction not found")
    await db.delete(reaction)
    await db.commit()

    await _broadcast_reactions(db, message_id)
    return {"detail": "Reaction removed"}


@router.get("/{message_id}", response_model=list[ReactionOut])
async def get_reactions(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_reactions(db, message_id, current_user.id)


async def _get_reactions(db: AsyncSession, message_id: uuid.UUID, current_user_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(Reaction).where(Reaction.message_id == message_id)
    )
    reactions = result.scalars().all()

    grouped: dict[str, list[str]] = {}
    for r in reactions:
        grouped.setdefault(r.emoji, []).append(str(r.user_id))

    return [
        ReactionOut(
            emoji=emoji, count=len(users), users=users,
            reacted_by_me=str(current_user_id) in users,
        )
        for emoji, users in grouped.items()
    ]


async def _broadcast_reactions(db: AsyncSession, message_id: uuid.UUID):
    from app.models.message import Message
    msg = await db.get(Message, message_id)
    if not msg:
        return

    result = await db.execute(select(Reaction).where(Reaction.message_id == message_id))
    reactions = result.scalars().all()
    grouped = {}
    for r in reactions:
        grouped.setdefault(r.emoji, []).append(str(r.user_id))

    data = {
        "message_id": str(message_id),
        "reactions": [{"emoji": e, "count": len(u), "users": u} for e, u in grouped.items()],
    }

    targets = set()
    if msg.receiver_id:
        targets.add(msg.sender_id)
        targets.add(msg.receiver_id)

    for uid in targets:
        await manager.send_to_user(uid, "reaction_update", data)
