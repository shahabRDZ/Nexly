import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.block import Block, Report, Session
from app.models.user import User

router = APIRouter(prefix="/moderation", tags=["moderation"])


# ── Block ──

@router.post("/block/{user_id}")
async def block_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    existing = await db.execute(
        select(Block).where(Block.blocker_id == current_user.id, Block.blocked_id == user_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already blocked")
    db.add(Block(blocker_id=current_user.id, blocked_id=user_id))
    await db.commit()
    return {"detail": "User blocked"}


@router.delete("/block/{user_id}")
async def unblock_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Block).where(Block.blocker_id == current_user.id, Block.blocked_id == user_id)
    )
    block = result.scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="Not blocked")
    await db.delete(block)
    await db.commit()
    return {"detail": "User unblocked"}


@router.get("/blocked")
async def list_blocked(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).join(Block, Block.blocked_id == User.id).where(Block.blocker_id == current_user.id)
    )
    users = result.scalars().all()
    return [{"id": str(u.id), "name": u.name, "phone": u.phone, "avatar_url": u.avatar_url} for u in users]


# ── Report ──

class ReportRequest(BaseModel):
    reported_user_id: uuid.UUID | None = None
    reported_message_id: uuid.UUID | None = None
    reason: str  # spam, abuse, harassment, other
    description: str | None = None


@router.post("/report")
async def create_report(
    body: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    db.add(Report(
        reporter_id=current_user.id,
        reported_user_id=body.reported_user_id,
        reported_message_id=body.reported_message_id,
        reason=body.reason,
        description=body.description,
    ))
    await db.commit()
    return {"detail": "Report submitted"}


# ── Sessions ──

@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).where(Session.user_id == current_user.id).order_by(Session.last_active.desc())
    )
    sessions = result.scalars().all()
    return [
        {"id": str(s.id), "device_name": s.device_name, "ip_address": s.ip_address,
         "last_active": s.last_active.isoformat(), "created_at": s.created_at.isoformat()}
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
async def terminate_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
    return {"detail": "Session terminated"}
