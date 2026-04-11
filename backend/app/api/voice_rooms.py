"""Voice Rooms — Live audio rooms like Clubhouse/Twitter Spaces."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.voice_room import VoiceRoom, VoiceRoomParticipant, RoomStatus
from app.models.user import User
from app.websocket.manager import manager

router = APIRouter(prefix="/voice-rooms", tags=["voice-rooms"])


class RoomCreate(BaseModel):
    title: str
    description: str = ""
    is_private: bool = False
    max_speakers: int = 10


class RoomOut(BaseModel):
    id: str; title: str; description: str; host_id: str
    status: str; speaker_count: int; listener_count: int
    is_private: bool; created_at: str


@router.post("/", response_model=RoomOut)
async def create_room(body: RoomCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    room = VoiceRoom(title=body.title, description=body.description, host_id=current_user.id, is_private=body.is_private, max_speakers=body.max_speakers)
    db.add(room)
    await db.flush()
    db.add(VoiceRoomParticipant(room_id=room.id, user_id=current_user.id, is_speaker=True, is_muted=False))
    await db.commit()
    await db.refresh(room)
    return _room_out(room, 1, 0)


@router.get("/live", response_model=list[RoomOut])
async def list_live_rooms(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VoiceRoom).where(VoiceRoom.status == RoomStatus.LIVE, VoiceRoom.is_private == False).order_by(VoiceRoom.created_at.desc()).limit(50))
    rooms = []
    for r in result.scalars().all():
        sc = (await db.execute(select(func.count()).where(VoiceRoomParticipant.room_id == r.id, VoiceRoomParticipant.is_speaker == True))).scalar()
        rooms.append(_room_out(r, sc, r.listener_count))
    return rooms


@router.post("/{room_id}/join")
async def join_room(room_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    room = await db.get(VoiceRoom, room_id)
    if not room or room.status != RoomStatus.LIVE:
        raise HTTPException(status_code=404, detail="Room not found or ended")
    existing = await db.execute(select(VoiceRoomParticipant).where(VoiceRoomParticipant.room_id == room_id, VoiceRoomParticipant.user_id == current_user.id))
    if existing.scalar_one_or_none():
        return {"detail": "Already in room"}
    db.add(VoiceRoomParticipant(room_id=room_id, user_id=current_user.id))
    room.listener_count += 1
    await db.commit()
    await _broadcast_room_update(db, room_id)
    return {"detail": "Joined as listener"}


@router.post("/{room_id}/leave")
async def leave_room(room_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VoiceRoomParticipant).where(VoiceRoomParticipant.room_id == room_id, VoiceRoomParticipant.user_id == current_user.id))
    participant = result.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=404, detail="Not in room")
    room = await db.get(VoiceRoom, room_id)
    if not participant.is_speaker:
        room.listener_count = max(0, room.listener_count - 1)
    await db.delete(participant)
    await db.commit()
    # If host leaves, end room
    if current_user.id == room.host_id:
        room.status = RoomStatus.ENDED
        room.ended_at = datetime.now(timezone.utc)
        await db.commit()
    await _broadcast_room_update(db, room_id)
    return {"detail": "Left room"}


@router.post("/{room_id}/raise-hand")
async def raise_hand(room_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VoiceRoomParticipant).where(VoiceRoomParticipant.room_id == room_id, VoiceRoomParticipant.user_id == current_user.id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Not in room")
    p.hand_raised = True
    await db.commit()
    await _broadcast_room_update(db, room_id)
    return {"detail": "Hand raised"}


@router.post("/{room_id}/promote/{user_id}")
async def promote_to_speaker(room_id: uuid.UUID, user_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    room = await db.get(VoiceRoom, room_id)
    if not room or room.host_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only host can promote")
    result = await db.execute(select(VoiceRoomParticipant).where(VoiceRoomParticipant.room_id == room_id, VoiceRoomParticipant.user_id == user_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="User not in room")
    p.is_speaker = True
    p.hand_raised = False
    p.is_muted = False
    room.listener_count = max(0, room.listener_count - 1)
    await db.commit()
    await _broadcast_room_update(db, room_id)
    return {"detail": "Promoted to speaker"}


@router.get("/{room_id}/participants")
async def get_participants(room_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(VoiceRoomParticipant, User).join(User, VoiceRoomParticipant.user_id == User.id).where(VoiceRoomParticipant.room_id == room_id)
    )
    return [
        {"user_id": str(u.id), "name": u.name, "avatar_url": u.avatar_url, "is_speaker": p.is_speaker, "is_muted": p.is_muted, "hand_raised": p.hand_raised}
        for p, u in result.all()
    ]


@router.post("/{room_id}/end")
async def end_room(room_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    room = await db.get(VoiceRoom, room_id)
    if not room or room.host_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only host can end")
    room.status = RoomStatus.ENDED
    room.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await _broadcast_room_update(db, room_id)
    return {"detail": "Room ended"}


def _room_out(r: VoiceRoom, sc: int, lc: int) -> RoomOut:
    return RoomOut(id=str(r.id), title=r.title, description=r.description, host_id=str(r.host_id), status=r.status.value, speaker_count=sc, listener_count=lc, is_private=r.is_private, created_at=r.created_at.isoformat())

async def _broadcast_room_update(db, room_id):
    result = await db.execute(select(VoiceRoomParticipant.user_id).where(VoiceRoomParticipant.room_id == room_id))
    for (uid,) in result.all():
        await manager.send_to_user(uid, "voice_room_update", {"room_id": str(room_id)})
