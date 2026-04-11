import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.call import Call, CallType, CallStatus
from app.models.user import User
from app.websocket.manager import manager

router = APIRouter(prefix="/calls", tags=["calls"])


class CallInitiate(BaseModel):
    callee_id: uuid.UUID
    call_type: str = "voice"


class CallOut(BaseModel):
    id: uuid.UUID
    caller_id: uuid.UUID
    callee_id: uuid.UUID
    call_type: str
    status: str
    duration_seconds: int | None
    started_at: str
    ended_at: str | None
    model_config = {"from_attributes": True}


class SDPOffer(BaseModel):
    call_id: uuid.UUID
    sdp: str
    type: str = "offer"


class ICECandidate(BaseModel):
    call_id: uuid.UUID
    candidate: str
    sdp_mid: str | None = None
    sdp_m_line_index: int | None = None


@router.post("/initiate", response_model=CallOut)
async def initiate_call(
    body: CallInitiate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a voice/video call. Sends call offer via WebSocket to callee."""
    callee = await db.get(User, body.callee_id)
    if not callee:
        raise HTTPException(status_code=404, detail="User not found")

    call = Call(
        caller_id=current_user.id,
        callee_id=body.callee_id,
        call_type=body.call_type,
        status=CallStatus.RINGING,
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)

    # Notify callee via WebSocket
    await manager.send_to_user(body.callee_id, "call_incoming", {
        "call_id": str(call.id),
        "caller_id": str(current_user.id),
        "caller_name": current_user.name,
        "caller_avatar": current_user.avatar_url,
        "call_type": body.call_type,
    })

    return _call_out(call)


@router.post("/{call_id}/answer")
async def answer_call(
    call_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    call = await db.get(Call, call_id)
    if not call or call.callee_id != current_user.id:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.status != CallStatus.RINGING:
        raise HTTPException(status_code=400, detail="Call is not ringing")

    call.status = CallStatus.ONGOING
    await db.commit()

    await manager.send_to_user(call.caller_id, "call_answered", {"call_id": str(call_id)})
    return {"detail": "Call answered"}


@router.post("/{call_id}/decline")
async def decline_call(
    call_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    call = await db.get(Call, call_id)
    if not call or call.callee_id != current_user.id:
        raise HTTPException(status_code=404, detail="Call not found")

    call.status = CallStatus.DECLINED
    call.ended_at = datetime.now(timezone.utc)
    await db.commit()

    await manager.send_to_user(call.caller_id, "call_declined", {"call_id": str(call_id)})
    return {"detail": "Call declined"}


@router.post("/{call_id}/end")
async def end_call(
    call_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    call = await db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if current_user.id not in (call.caller_id, call.callee_id):
        raise HTTPException(status_code=403, detail="Not in this call")

    call.status = CallStatus.ENDED
    call.ended_at = datetime.now(timezone.utc)
    if call.started_at:
        call.duration_seconds = int((call.ended_at - call.started_at).total_seconds())
    await db.commit()

    other_id = call.callee_id if current_user.id == call.caller_id else call.caller_id
    await manager.send_to_user(other_id, "call_ended", {
        "call_id": str(call_id),
        "duration": call.duration_seconds,
    })
    return {"detail": "Call ended", "duration": call.duration_seconds}


# ── WebRTC Signaling ──


@router.post("/signal/offer")
async def send_offer(
    body: SDPOffer,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    call = await db.get(Call, body.call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    other_id = call.callee_id if current_user.id == call.caller_id else call.caller_id
    await manager.send_to_user(other_id, "webrtc_offer", {
        "call_id": str(body.call_id), "sdp": body.sdp, "type": body.type,
    })
    return {"detail": "Offer sent"}


@router.post("/signal/answer")
async def send_answer(
    body: SDPOffer,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    call = await db.get(Call, body.call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    other_id = call.callee_id if current_user.id == call.caller_id else call.caller_id
    await manager.send_to_user(other_id, "webrtc_answer", {
        "call_id": str(body.call_id), "sdp": body.sdp, "type": "answer",
    })
    return {"detail": "Answer sent"}


@router.post("/signal/ice")
async def send_ice_candidate(
    body: ICECandidate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    call = await db.get(Call, body.call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    other_id = call.callee_id if current_user.id == call.caller_id else call.caller_id
    await manager.send_to_user(other_id, "webrtc_ice", {
        "call_id": str(body.call_id), "candidate": body.candidate,
        "sdp_mid": body.sdp_mid, "sdp_m_line_index": body.sdp_m_line_index,
    })
    return {"detail": "ICE candidate sent"}


# ── History ──


@router.get("/history", response_model=list[CallOut])
async def call_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Call)
        .where(or_(Call.caller_id == current_user.id, Call.callee_id == current_user.id))
        .order_by(Call.started_at.desc())
        .limit(limit)
    )
    return [_call_out(c) for c in result.scalars().all()]


def _call_out(call: Call) -> CallOut:
    return CallOut(
        id=call.id, caller_id=call.caller_id, callee_id=call.callee_id,
        call_type=call.call_type.value if hasattr(call.call_type, 'value') else call.call_type,
        status=call.status.value if hasattr(call.status, 'value') else call.status,
        duration_seconds=call.duration_seconds,
        started_at=call.started_at.isoformat(),
        ended_at=call.ended_at.isoformat() if call.ended_at else None,
    )
