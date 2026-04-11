"""Innovative features — Anonymous Rooms, Premium Messages, Whiteboard, Playlists, Chat Recap, Mood Theme."""
import json
import random
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.innovative import (
    AnonymousRoom, AnonymousParticipant, PremiumMessage, PremiumUnlock,
    Whiteboard, Playlist, PlaylistTrack, ChatRecap,
)
from app.models.message import Message
from app.models.user import User

router = APIRouter(tags=["innovative"])

ANON_NAMES = ["Shadow", "Phoenix", "Ghost", "Raven", "Storm", "Cipher", "Echo", "Nebula", "Spark", "Drift",
              "Mystic", "Blaze", "Frost", "Pixel", "Wave", "Orbit", "Zen", "Nova", "Pulse", "Wisp"]


# ═══════ Anonymous Chat Rooms ═══════

class AnonRoomCreate(BaseModel):
    topic: str
    max_participants: int = 50
    hours: int = 24


@router.post("/anonymous-rooms")
async def create_anon_room(body: AnonRoomCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    room = AnonymousRoom(topic=body.topic, max_participants=body.max_participants, expires_at=datetime.now(timezone.utc) + timedelta(hours=body.hours))
    db.add(room)
    await db.flush()
    alias = f"{random.choice(ANON_NAMES)}_{random.randint(100,999)}"
    db.add(AnonymousParticipant(room_id=room.id, user_id=current_user.id, alias=alias))
    room.active_count = 1
    await db.commit()
    return {"id": str(room.id), "topic": room.topic, "your_alias": alias, "expires_at": room.expires_at.isoformat()}


@router.get("/anonymous-rooms")
async def list_anon_rooms(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AnonymousRoom).where(AnonymousRoom.expires_at > datetime.now(timezone.utc)).order_by(AnonymousRoom.created_at.desc()).limit(30))
    return [{"id": str(r.id), "topic": r.topic, "active_count": r.active_count, "expires_at": r.expires_at.isoformat()} for r in result.scalars().all()]


@router.post("/anonymous-rooms/{room_id}/join")
async def join_anon_room(room_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    room = await db.get(AnonymousRoom, room_id)
    if not room or room.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="Room expired or not found")
    existing = await db.execute(select(AnonymousParticipant).where(AnonymousParticipant.room_id == room_id, AnonymousParticipant.user_id == current_user.id))
    if existing.scalar_one_or_none():
        return {"detail": "Already in room"}
    alias = f"{random.choice(ANON_NAMES)}_{random.randint(100,999)}"
    db.add(AnonymousParticipant(room_id=room_id, user_id=current_user.id, alias=alias))
    room.active_count += 1
    await db.commit()
    return {"your_alias": alias}


# ═══════ Pay-Per-Message ═══════

class PremiumCreate(BaseModel):
    receiver_id: uuid.UUID
    content: str
    preview_text: str | None = None
    price: float
    currency: str = "USD"


@router.post("/premium-messages")
async def create_premium_msg(body: PremiumCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.services.message_service import save_message
    msg = await save_message(db, sender_id=current_user.id, receiver_id=body.receiver_id, content=body.content, message_type="text")
    pm = PremiumMessage(message_id=msg.id, price=body.price, currency=body.currency, preview_text=body.preview_text)
    db.add(pm)
    await db.commit()
    return {"id": str(pm.id), "message_id": str(msg.id), "price": body.price, "preview": body.preview_text}


@router.post("/premium-messages/{premium_id}/unlock")
async def unlock_premium(premium_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pm = await db.get(PremiumMessage, premium_id)
    if not pm:
        raise HTTPException(status_code=404)
    existing = await db.execute(select(PremiumUnlock).where(PremiumUnlock.premium_id == premium_id, PremiumUnlock.user_id == current_user.id))
    if existing.scalar_one_or_none():
        msg = await db.get(Message, pm.message_id)
        return {"content": msg.content, "already_unlocked": True}
    # In production: charge payment here
    db.add(PremiumUnlock(premium_id=premium_id, user_id=current_user.id))
    pm.total_unlocks += 1
    pm.total_revenue += pm.price
    await db.commit()
    msg = await db.get(Message, pm.message_id)
    return {"content": msg.content, "unlocked": True}


# ═══════ Collaborative Whiteboard ═══════

class WhiteboardCreate(BaseModel):
    title: str = "Untitled"
    chat_user_id: uuid.UUID | None = None
    group_id: uuid.UUID | None = None


class WhiteboardUpdate(BaseModel):
    canvas_data: str  # JSON strokes


@router.post("/whiteboards")
async def create_whiteboard(body: WhiteboardCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    wb = Whiteboard(title=body.title, creator_id=current_user.id, chat_user_id=body.chat_user_id, group_id=body.group_id)
    db.add(wb)
    await db.commit()
    await db.refresh(wb)
    return {"id": str(wb.id), "title": wb.title}


@router.get("/whiteboards/{wb_id}")
async def get_whiteboard(wb_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    wb = await db.get(Whiteboard, wb_id)
    if not wb:
        raise HTTPException(status_code=404)
    return {"id": str(wb.id), "title": wb.title, "canvas_data": wb.canvas_data, "updated_at": wb.updated_at.isoformat()}


@router.patch("/whiteboards/{wb_id}")
async def update_whiteboard(wb_id: uuid.UUID, body: WhiteboardUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    wb = await db.get(Whiteboard, wb_id)
    if not wb:
        raise HTTPException(status_code=404)
    wb.canvas_data = body.canvas_data
    await db.commit()
    # Broadcast to collaborators via WS
    from app.websocket.manager import manager
    targets = set()
    if wb.chat_user_id:
        targets.add(wb.chat_user_id)
    targets.add(wb.creator_id)
    for uid in targets:
        if uid != current_user.id:
            await manager.send_to_user(uid, "whiteboard_update", {"whiteboard_id": str(wb_id)})
    return {"detail": "Updated"}


# ═══════ Collaborative Playlists ═══════

class PlaylistCreate(BaseModel):
    title: str
    group_id: uuid.UUID | None = None
    chat_user_id: uuid.UUID | None = None


class TrackAdd(BaseModel):
    title: str
    artist: str = ""
    url: str
    duration_seconds: int | None = None


@router.post("/playlists")
async def create_playlist(body: PlaylistCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pl = Playlist(title=body.title, creator_id=current_user.id, group_id=body.group_id, chat_user_id=body.chat_user_id)
    db.add(pl)
    await db.commit()
    return {"id": str(pl.id), "title": pl.title}


@router.get("/playlists/{playlist_id}")
async def get_playlist(playlist_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pl = await db.get(Playlist, playlist_id)
    if not pl:
        raise HTTPException(status_code=404)
    tracks_r = await db.execute(select(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id).order_by(PlaylistTrack.added_at.asc()))
    tracks = [{"id": str(t.id), "title": t.title, "artist": t.artist, "url": t.url, "duration": t.duration_seconds} for t in tracks_r.scalars().all()]
    return {"id": str(pl.id), "title": pl.title, "tracks": tracks}


@router.post("/playlists/{playlist_id}/tracks")
async def add_track(playlist_id: uuid.UUID, body: TrackAdd, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pl = await db.get(Playlist, playlist_id)
    if not pl:
        raise HTTPException(status_code=404)
    track = PlaylistTrack(playlist_id=playlist_id, added_by=current_user.id, title=body.title, artist=body.artist, url=body.url, duration_seconds=body.duration_seconds)
    db.add(track)
    await db.commit()
    return {"id": str(track.id), "title": track.title}


@router.delete("/playlists/{playlist_id}/tracks/{track_id}")
async def remove_track(playlist_id: uuid.UUID, track_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    track = await db.get(PlaylistTrack, track_id)
    if not track or track.playlist_id != playlist_id:
        raise HTTPException(status_code=404)
    await db.delete(track)
    await db.commit()
    return {"detail": "Removed"}


# ═══════ Chat Recap (Daily Digest) ═══════

@router.post("/recap/generate")
async def generate_recap(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Generate AI recap of yesterday's conversations."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0) - timedelta(days=1)
    yesterday_end = yesterday_start + timedelta(days=1)

    # Check if already generated
    existing = await db.execute(select(ChatRecap).where(ChatRecap.user_id == current_user.id, ChatRecap.recap_date == today))
    if existing.scalar_one_or_none():
        return {"detail": "Recap already exists for today"}

    # Get yesterday's messages
    result = await db.execute(
        select(Message).where(
            or_(Message.sender_id == current_user.id, Message.receiver_id == current_user.id),
            Message.created_at >= yesterday_start, Message.created_at < yesterday_end,
            Message.message_type == "text", Message.deleted_for_all == False,
        ).order_by(Message.created_at.asc()).limit(500)
    )
    messages = result.scalars().all()

    if not messages:
        return {"summary": "No messages yesterday.", "message_count": 0}

    # Count unique chats
    chat_partners = set()
    for m in messages:
        if m.receiver_id: chat_partners.add(m.receiver_id if m.sender_id == current_user.id else m.sender_id)

    # Build summary
    texts = [m.content for m in messages if m.content]
    highlights = texts[:5] if len(texts) > 5 else texts

    # Detect mood
    positive_words = {"good", "great", "awesome", "love", "happy", "thanks", "عالی", "خوب", "ممنون", "❤️", "😊"}
    negative_words = {"bad", "sad", "sorry", "angry", "بد", "ناراحت", "متأسف"}
    pos_count = sum(1 for t in texts for w in positive_words if w in t.lower())
    neg_count = sum(1 for t in texts for w in negative_words if w in t.lower())
    mood = "positive" if pos_count > neg_count else "negative" if neg_count > pos_count else "neutral"

    lang = current_user.preferred_language
    if lang == "fa":
        summary = f"دیروز {len(messages)} پیام در {len(chat_partners)} مکالمه داشتید. حال و هوای کلی: {'مثبت 😊' if mood == 'positive' else 'خنثی 😐' if mood == 'neutral' else 'کمی غمگین 😔'}"
    else:
        summary = f"Yesterday you had {len(messages)} messages across {len(chat_partners)} conversations. Overall mood: {'positive 😊' if mood == 'positive' else 'neutral 😐' if mood == 'neutral' else 'a bit down 😔'}"

    recap = ChatRecap(
        user_id=current_user.id, recap_date=today, summary=summary,
        highlights=json.dumps(highlights[:5]), message_count=len(messages),
        chat_count=len(chat_partners), mood=mood,
    )
    db.add(recap)
    await db.commit()

    return {"summary": summary, "message_count": len(messages), "chat_count": len(chat_partners), "mood": mood, "highlights": highlights[:5]}


@router.get("/recap")
async def get_recaps(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatRecap).where(ChatRecap.user_id == current_user.id).order_by(ChatRecap.recap_date.desc()).limit(7))
    return [
        {"date": r.recap_date, "summary": r.summary, "message_count": r.message_count, "chat_count": r.chat_count, "mood": r.mood,
         "highlights": json.loads(r.highlights) if r.highlights else []}
        for r in result.scalars().all()
    ]


# ═══════ Mood-Based Chat Theme ═══════

@router.post("/mood/analyze")
async def analyze_mood(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Analyze recent messages to suggest a chat theme based on mood."""
    since = datetime.now(timezone.utc) - timedelta(hours=6)
    result = await db.execute(
        select(Message.content).where(
            Message.sender_id == current_user.id, Message.created_at > since,
            Message.message_type == "text", Message.content != None,
        ).limit(50)
    )
    texts = [r[0] for r in result.all() if r[0]]

    if not texts:
        return {"mood": "neutral", "theme": "default", "color": "#6C5CE7"}

    all_text = " ".join(texts).lower()

    moods = {
        "happy": ({"happy", "great", "love", "awesome", "عالی", "خوشحال", "😊", "❤️", "🎉"}, "#00B894", "spring"),
        "chill": ({"chill", "relax", "calm", "peace", "آروم", "😌"}, "#00CEC9", "ocean"),
        "energetic": ({"let's go", "excited", "fire", "🔥", "💪", "هیجان"}, "#E17055", "sunset"),
        "romantic": ({"miss you", "love", "heart", "دلتنگ", "عشق", "❤️", "💕"}, "#E84393", "rose"),
        "sad": ({"sad", "miss", "alone", "ناراحت", "تنها", "😢"}, "#636E72", "rain"),
        "productive": ({"work", "meeting", "done", "کار", "جلسه", "✅"}, "#2D3436", "dark"),
    }

    best_mood, best_score = "neutral", 0
    for mood, (keywords, _, _) in moods.items():
        score = sum(1 for k in keywords if k in all_text)
        if score > best_score:
            best_mood, best_score = mood, score

    if best_mood in moods:
        _, color, theme = moods[best_mood]
    else:
        color, theme = "#6C5CE7", "default"

    return {"mood": best_mood, "theme": theme, "color": color, "confidence": min(best_score / 3, 1.0)}
