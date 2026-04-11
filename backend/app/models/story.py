import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StoryType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    TEXT = "text"


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    story_type: Mapped[StoryType] = mapped_column(Enum(StoryType), default=StoryType.IMAGE)
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text_content: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bg_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StoryView(Base):
    __tablename__ = "story_views"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
