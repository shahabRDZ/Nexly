import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.poll import Poll, PollOption, PollVote
from app.models.user import User

router = APIRouter(prefix="/polls", tags=["polls"])


class PollCreate(BaseModel):
    group_id: uuid.UUID | None = None
    channel_id: uuid.UUID | None = None
    question: str
    options: list[str]
    multiple_choice: bool = False
    anonymous: bool = False


class PollOut(BaseModel):
    id: uuid.UUID
    question: str
    creator_id: uuid.UUID
    multiple_choice: bool
    anonymous: bool
    closed: bool
    options: list[dict]
    total_votes: int
    my_votes: list[str]


@router.post("/", response_model=PollOut)
async def create_poll(
    body: PollCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if len(body.options) < 2:
        raise HTTPException(status_code=400, detail="At least 2 options required")

    poll = Poll(
        group_id=body.group_id, channel_id=body.channel_id,
        creator_id=current_user.id, question=body.question,
        multiple_choice=body.multiple_choice, anonymous=body.anonymous,
    )
    db.add(poll)
    await db.flush()

    for text in body.options:
        db.add(PollOption(poll_id=poll.id, text=text))
    await db.commit()

    return await _poll_out(db, poll.id, current_user.id)


@router.post("/{poll_id}/vote/{option_id}")
async def vote(
    poll_id: uuid.UUID,
    option_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    poll = await db.get(Poll, poll_id)
    if not poll or poll.closed:
        raise HTTPException(status_code=400, detail="Poll not available")

    if not poll.multiple_choice:
        existing = await db.execute(
            select(PollVote).where(PollVote.poll_id == poll_id, PollVote.user_id == current_user.id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Already voted")

    option = await db.get(PollOption, option_id)
    if not option or option.poll_id != poll_id:
        raise HTTPException(status_code=404, detail="Option not found")

    db.add(PollVote(poll_id=poll_id, option_id=option_id, user_id=current_user.id))
    option.vote_count += 1
    await db.commit()

    return await _poll_out(db, poll_id, current_user.id)


@router.get("/{poll_id}", response_model=PollOut)
async def get_poll(
    poll_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _poll_out(db, poll_id, current_user.id)


@router.post("/{poll_id}/close")
async def close_poll(
    poll_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    poll = await db.get(Poll, poll_id)
    if not poll or poll.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not poll creator")
    poll.closed = True
    await db.commit()
    return {"detail": "Poll closed"}


async def _poll_out(db: AsyncSession, poll_id: uuid.UUID, user_id: uuid.UUID) -> PollOut:
    poll = await db.get(Poll, poll_id)
    options_r = await db.execute(select(PollOption).where(PollOption.poll_id == poll_id))
    options = options_r.scalars().all()

    my_votes_r = await db.execute(
        select(PollVote.option_id).where(PollVote.poll_id == poll_id, PollVote.user_id == user_id)
    )
    my_votes = [str(r[0]) for r in my_votes_r.all()]

    total = sum(o.vote_count for o in options)
    return PollOut(
        id=poll.id, question=poll.question, creator_id=poll.creator_id,
        multiple_choice=poll.multiple_choice, anonymous=poll.anonymous, closed=poll.closed,
        options=[{"id": str(o.id), "text": o.text, "vote_count": o.vote_count} for o in options],
        total_votes=total, my_votes=my_votes,
    )
