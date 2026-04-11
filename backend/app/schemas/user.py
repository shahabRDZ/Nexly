import uuid
from datetime import datetime

from pydantic import BaseModel


class UserProfile(BaseModel):
    id: uuid.UUID
    phone: str
    name: str
    avatar_url: str | None
    status_text: str
    is_online: bool
    last_seen: datetime | None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: str | None = None
    status_text: str | None = None


class UserSearch(BaseModel):
    query: str
