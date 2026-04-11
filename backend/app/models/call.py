import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CallType(str, enum.Enum):
    VOICE = "voice"
    VIDEO = "video"


class CallStatus(str, enum.Enum):
    RINGING = "ringing"
    ONGOING = "ongoing"
    ENDED = "ended"
    MISSED = "missed"
    DECLINED = "declined"


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    callee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    call_type: Mapped[CallType] = mapped_column(Enum(CallType), default=CallType.VOICE)
    status: Mapped[CallStatus] = mapped_column(Enum(CallStatus), default=CallStatus.RINGING)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CallICECandidate(Base):
    """Store ICE candidates for WebRTC signaling."""
    __tablename__ = "call_ice_candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    from_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    candidate: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
