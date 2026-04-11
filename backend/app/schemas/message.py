import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.message import MessageStatus, MessageType


class MessageCreate(BaseModel):
    receiver_id: uuid.UUID
    content: str | None = None
    message_type: MessageType = MessageType.TEXT
    reply_to_id: uuid.UUID | None = None


class MessageOut(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    receiver_id: uuid.UUID | None
    group_id: uuid.UUID | None = None
    channel_id: uuid.UUID | None = None
    content: str | None
    original_content: str | None = None
    source_language: str | None = None
    translated: bool = False
    message_type: MessageType
    media_url: str | None
    media_thumbnail: str | None = None
    media_size: int | None = None
    media_name: str | None = None
    status: MessageStatus
    reply_to_id: uuid.UUID | None = None
    is_forwarded: bool = False
    is_pinned: bool = False
    deleted_for_all: bool = False
    created_at: datetime
    edited_at: datetime | None = None

    model_config = {"from_attributes": True}


class MessageStatusUpdate(BaseModel):
    message_ids: list[uuid.UUID]
    status: MessageStatus


class ConversationPreview(BaseModel):
    user: "UserPreview"
    last_message: MessageOut | None
    unread_count: int


class UserPreview(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    avatar_url: str | None
    is_online: bool

    model_config = {"from_attributes": True}


class WSMessage(BaseModel):
    event: str
    data: dict
