import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status_text: Mapped[str] = mapped_column(String(200), nullable=False, default="Hey, I'm using Nexly!")
    is_online: Mapped[bool] = mapped_column(default=False)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Security
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    two_fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Encryption
    public_key: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
