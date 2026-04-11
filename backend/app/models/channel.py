import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Boolean, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    username: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    creator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChannelSubscriber(Base):
    __tablename__ = "channel_subscribers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
