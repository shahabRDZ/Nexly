"""Smart Schedule — AI extracts events from chats + scheduled messages."""
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.schedule import ScheduleEvent, ScheduledMessage
from app.models.message import Message
from app.models.user import User

router = APIRouter(prefix="/schedule", tags=["schedule"])


# ── AI Event Extraction ──

class ScanRequest(BaseModel):
    conversation_user_id: uuid.UUID | None = None
    group_id: uuid.UUID | None = None
    hours: int = 48


@router.post("/scan")
async def scan_for_events(body: ScanRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """AI scans recent messages and extracts date/time references as events."""
    since = datetime.now(timezone.utc) - timedelta(hours=body.hours)
    q = select(Message).where(Message.created_at > since, Message.message_type == "text", Message.deleted_for_all == False)

    if body.conversation_user_id:
        q = q.where(or_(
            and_(Message.sender_id == current_user.id, Message.receiver_id == body.conversation_user_id),
            and_(Message.sender_id == body.conversation_user_id, Message.receiver_id == current_user.id),
        ))
    elif body.group_id:
        q = q.where(Message.group_id == body.group_id)
    else:
        q = q.where(or_(Message.sender_id == current_user.id, Message.receiver_id == current_user.id))

    result = await db.execute(q.order_by(Message.created_at.asc()).limit(200))
    messages = result.scalars().all()

    events = []
    now = datetime.now(timezone.utc)
    for msg in messages:
        if not msg.content:
            continue
        extracted = _extract_time_references(msg.content, now)
        for title, event_time in extracted:
            existing = await db.execute(
                select(ScheduleEvent).where(ScheduleEvent.user_id == current_user.id, ScheduleEvent.title == title, ScheduleEvent.event_time == event_time)
            )
            if not existing.scalar_one_or_none():
                evt = ScheduleEvent(user_id=current_user.id, title=title, event_time=event_time, source_message_id=msg.id, ai_extracted=True)
                db.add(evt)
                events.append({"title": title, "event_time": event_time.isoformat(), "source": msg.content[:100]})

    await db.commit()
    return {"events_found": len(events), "events": events}


# ── Manual Events ──

class EventCreate(BaseModel):
    title: str
    description: str | None = None
    event_time: datetime


@router.post("/events")
async def create_event(body: EventCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    evt = ScheduleEvent(user_id=current_user.id, title=body.title, description=body.description, event_time=body.event_time)
    db.add(evt)
    await db.commit()
    await db.refresh(evt)
    return {"id": str(evt.id), "title": evt.title, "event_time": evt.event_time.isoformat()}


@router.get("/events")
async def list_events(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ScheduleEvent).where(ScheduleEvent.user_id == current_user.id, ScheduleEvent.event_time > datetime.now(timezone.utc)).order_by(ScheduleEvent.event_time.asc()).limit(50)
    )
    return [{"id": str(e.id), "title": e.title, "description": e.description, "event_time": e.event_time.isoformat(), "ai_extracted": e.ai_extracted} for e in result.scalars().all()]


@router.delete("/events/{event_id}")
async def delete_event(event_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    evt = await db.get(ScheduleEvent, event_id)
    if not evt or evt.user_id != current_user.id:
        raise HTTPException(status_code=404)
    await db.delete(evt)
    await db.commit()
    return {"detail": "Deleted"}


# ── Scheduled Messages ──

class ScheduleMessageRequest(BaseModel):
    receiver_id: uuid.UUID | None = None
    group_id: uuid.UUID | None = None
    content: str
    send_at: datetime


@router.post("/messages")
async def schedule_message(body: ScheduleMessageRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sm = ScheduledMessage(sender_id=current_user.id, receiver_id=body.receiver_id, group_id=body.group_id, content=body.content, send_at=body.send_at)
    db.add(sm)
    await db.commit()
    return {"id": str(sm.id), "send_at": sm.send_at.isoformat(), "content": sm.content}


@router.get("/messages")
async def list_scheduled(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScheduledMessage).where(ScheduledMessage.sender_id == current_user.id, ScheduledMessage.sent == False).order_by(ScheduledMessage.send_at.asc()))
    return [{"id": str(m.id), "receiver_id": str(m.receiver_id) if m.receiver_id else None, "content": m.content, "send_at": m.send_at.isoformat()} for m in result.scalars().all()]


@router.delete("/messages/{msg_id}")
async def cancel_scheduled(msg_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    m = await db.get(ScheduledMessage, msg_id)
    if not m or m.sender_id != current_user.id:
        raise HTTPException(status_code=404)
    await db.delete(m)
    await db.commit()
    return {"detail": "Cancelled"}


# ── AI Time Extraction ──

_TIME_PATTERNS = [
    (r"(?:at|@)\s*(\d{1,2}):(\d{2})", None),
    (r"(?:tomorrow|فردا)\s*(?:at|ساعت)?\s*(\d{1,2}):?(\d{2})?", 1),
    (r"(?:tonight|امشب)\s*(?:at|ساعت)?\s*(\d{1,2}):?(\d{2})?", 0),
    (r"(?:in|تا)\s*(\d+)\s*(?:hours?|ساعت)", None),
    (r"(?:in|تا)\s*(\d+)\s*(?:minutes?|دقیقه)", None),
]

def _extract_time_references(text: str, now: datetime) -> list[tuple[str, datetime]]:
    results = []
    lower = text.lower()

    # "tomorrow at HH:MM" / "فردا ساعت HH"
    m = re.search(r"(?:tomorrow|فردا)\s*(?:at|ساعت)?\s*(\d{1,2}):?(\d{2})?", lower)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        t = (now + timedelta(days=1)).replace(hour=h, minute=mi, second=0, microsecond=0)
        results.append((text[:80], t))

    # "at HH:MM" today
    m = re.search(r"(?:at|ساعت)\s*(\d{1,2}):(\d{2})", lower)
    if m and not results:
        h, mi = int(m.group(1)), int(m.group(2))
        t = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if t < now:
            t += timedelta(days=1)
        results.append((text[:80], t))

    # "in N hours"
    m = re.search(r"(?:in|تا)\s*(\d+)\s*(?:hours?|ساعت)", lower)
    if m and not results:
        results.append((text[:80], now + timedelta(hours=int(m.group(1)))))

    return results
