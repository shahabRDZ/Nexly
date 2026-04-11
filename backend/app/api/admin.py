"""Admin panel & analytics endpoints."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.message import Message
from app.models.group import Group
from app.models.channel import Channel
from app.models.call import Call
from app.models.block import Report

router = APIRouter(prefix="/admin", tags=["admin"])

# In production, add proper admin role checking
ADMIN_PHONES = {"+14155551234"}  # Configurable


async def _require_admin(current_user: User = Depends(get_current_user)):
    if current_user.phone not in ADMIN_PHONES:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── Dashboard ──

@router.get("/dashboard")
async def get_dashboard(
    admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    total_users = (await db.execute(select(func.count(User.id)))).scalar()
    today_users = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= today)
    )).scalar()
    online_users = (await db.execute(
        select(func.count(User.id)).where(User.is_online == True)
    )).scalar()
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar()
    today_messages = (await db.execute(
        select(func.count(Message.id)).where(Message.created_at >= today)
    )).scalar()
    total_groups = (await db.execute(select(func.count(Group.id)))).scalar()
    total_channels = (await db.execute(select(func.count(Channel.id)))).scalar()
    total_calls = (await db.execute(select(func.count(Call.id)))).scalar()
    pending_reports = (await db.execute(
        select(func.count(Report.id)).where(Report.resolved == False)
    )).scalar()

    return {
        "users": {"total": total_users, "today": today_users, "online": online_users},
        "messages": {"total": total_messages, "today": today_messages},
        "groups": total_groups,
        "channels": total_channels,
        "calls": total_calls,
        "reports_pending": pending_reports,
    }


# ── Analytics ──

@router.get("/analytics/messages")
async def message_analytics(
    days: int = 7,
    admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Message count per day for the last N days."""
    data = []
    now = datetime.now(timezone.utc)
    for i in range(days):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = (await db.execute(
            select(func.count(Message.id)).where(Message.created_at >= day_start, Message.created_at < day_end)
        )).scalar()
        data.append({"date": day_start.strftime("%Y-%m-%d"), "count": count})
    return list(reversed(data))


@router.get("/analytics/users")
async def user_analytics(
    days: int = 7,
    admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """New users per day."""
    data = []
    now = datetime.now(timezone.utc)
    for i in range(days):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = (await db.execute(
            select(func.count(User.id)).where(User.created_at >= day_start, User.created_at < day_end)
        )).scalar()
        data.append({"date": day_start.strftime("%Y-%m-%d"), "count": count})
    return list(reversed(data))


# ── User Management ──

@router.get("/users")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    search: str = "",
    admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(User)
    if search:
        q = q.where(User.name.ilike(f"%{search}%") | User.phone.ilike(f"%{search}%"))
    q = q.order_by(User.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    users = result.scalars().all()
    return [
        {"id": str(u.id), "name": u.name, "phone": u.phone, "avatar_url": u.avatar_url,
         "language": u.preferred_language, "is_online": u.is_online,
         "created_at": u.created_at.isoformat()}
        for u in users
    ]


# ── Reports ──

@router.get("/reports")
async def list_reports(
    admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Report).where(Report.resolved == False).order_by(Report.created_at.desc()).limit(50)
    )
    reports = result.scalars().all()
    return [
        {"id": str(r.id), "reporter_id": str(r.reporter_id),
         "reported_user_id": str(r.reported_user_id) if r.reported_user_id else None,
         "reason": r.reason, "description": r.description,
         "created_at": r.created_at.isoformat()}
        for r in reports
    ]


@router.post("/reports/{report_id}/resolve")
async def resolve_report(
    report_id: uuid.UUID,
    admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report.resolved = True
    await db.commit()
    return {"detail": "Report resolved"}
