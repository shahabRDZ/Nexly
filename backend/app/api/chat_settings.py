"""Per-chat user settings: pin, archive, mute, folder organization."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.chat_settings import ChatFolder, ChatSettings
from app.models.group import GroupMember
from app.models.user import User

router = APIRouter(prefix="/chat-settings", tags=["chat-settings"])


# ── Schemas ──

class FolderCreate(BaseModel):
    name: str
    icon: str | None = None


class FolderOut(BaseModel):
    id: uuid.UUID
    name: str
    icon: str | None
    position: int

    model_config = {"from_attributes": True}


class ChatSettingsOut(BaseModel):
    partner_id: uuid.UUID | None
    group_id: uuid.UUID | None
    is_pinned: bool
    is_archived: bool
    is_muted: bool
    muted_until: datetime | None
    folder_id: uuid.UUID | None


class MuteRequest(BaseModel):
    hours: int | None = None  # None = forever


class FolderAssignRequest(BaseModel):
    folder_id: uuid.UUID | None  # null to remove


# ── Helpers ──


async def _get_or_create_settings(
    db: AsyncSession,
    user_id: uuid.UUID,
    partner_id: uuid.UUID | None,
    group_id: uuid.UUID | None,
) -> ChatSettings:
    if (partner_id is None) == (group_id is None):
        raise HTTPException(status_code=400, detail="Provide exactly one of partner_id or group_id")

    # Validate membership for group chats
    if group_id:
        member = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id, GroupMember.user_id == user_id
            )
        )
        if not member.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a group member")

    q = select(ChatSettings).where(
        ChatSettings.user_id == user_id,
        ChatSettings.partner_id == partner_id,
        ChatSettings.group_id == group_id,
    )
    row = (await db.execute(q)).scalar_one_or_none()
    if row:
        return row
    row = ChatSettings(user_id=user_id, partner_id=partner_id, group_id=group_id)
    db.add(row)
    await db.flush()
    return row


def _to_out(row: ChatSettings) -> ChatSettingsOut:
    now = datetime.now(timezone.utc)
    muted = bool(row.muted_until) and (
        row.muted_until.replace(tzinfo=timezone.utc) > now
        if row.muted_until.tzinfo is None
        else row.muted_until > now
    )
    return ChatSettingsOut(
        partner_id=row.partner_id,
        group_id=row.group_id,
        is_pinned=row.is_pinned,
        is_archived=row.is_archived,
        is_muted=muted,
        muted_until=row.muted_until,
        folder_id=row.folder_id,
    )


# ── Folders CRUD ──


@router.get("/folders", response_model=list[FolderOut])
async def list_folders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(ChatFolder).where(ChatFolder.user_id == current_user.id).order_by(
        ChatFolder.position, ChatFolder.created_at
    )
    rows = (await db.execute(q)).scalars().all()
    return rows


@router.post("/folders", response_model=FolderOut)
async def create_folder(
    body: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Folder name required")
    if len(name) > 60:
        raise HTTPException(status_code=400, detail="Folder name too long (max 60)")

    count_q = select(ChatFolder).where(ChatFolder.user_id == current_user.id)
    existing = (await db.execute(count_q)).scalars().all()
    if len(existing) >= 20:
        raise HTTPException(status_code=400, detail="Maximum 20 folders allowed")

    folder = ChatFolder(
        user_id=current_user.id, name=name, icon=body.icon, position=len(existing)
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


@router.patch("/folders/{folder_id}", response_model=FolderOut)
async def update_folder(
    folder_id: uuid.UUID,
    body: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    folder = await db.get(ChatFolder, folder_id)
    if not folder or folder.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Folder not found")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Folder name required")
    folder.name = name[:60]
    folder.icon = body.icon
    await db.commit()
    await db.refresh(folder)
    return folder


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    folder = await db.get(ChatFolder, folder_id)
    if not folder or folder.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Unassign settings pointing at this folder
    rows = await db.execute(
        select(ChatSettings).where(
            ChatSettings.user_id == current_user.id, ChatSettings.folder_id == folder_id
        )
    )
    for s in rows.scalars().all():
        s.folder_id = None

    await db.delete(folder)
    await db.commit()
    return {"detail": "Folder deleted"}


# ── Per-chat settings list ──


@router.get("/", response_model=list[ChatSettingsOut])
async def list_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(ChatSettings).where(ChatSettings.user_id == current_user.id)
    rows = (await db.execute(q)).scalars().all()
    return [_to_out(r) for r in rows]


# ── Pin ──


@router.post("/pin")
async def pin_chat(
    partner_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_create_settings(db, current_user.id, partner_id, group_id)
    row.is_pinned = True
    row.pinned_at = datetime.now(timezone.utc)
    # Pinning an archived chat unarchives it
    row.is_archived = False
    row.archived_at = None
    await db.commit()
    return {"detail": "Chat pinned"}


@router.delete("/pin")
async def unpin_chat(
    partner_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_create_settings(db, current_user.id, partner_id, group_id)
    row.is_pinned = False
    row.pinned_at = None
    await db.commit()
    return {"detail": "Chat unpinned"}


# ── Archive ──


@router.post("/archive")
async def archive_chat(
    partner_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_create_settings(db, current_user.id, partner_id, group_id)
    row.is_archived = True
    row.archived_at = datetime.now(timezone.utc)
    # Archiving removes the pin
    row.is_pinned = False
    row.pinned_at = None
    await db.commit()
    return {"detail": "Chat archived"}


@router.delete("/archive")
async def unarchive_chat(
    partner_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_create_settings(db, current_user.id, partner_id, group_id)
    row.is_archived = False
    row.archived_at = None
    await db.commit()
    return {"detail": "Chat unarchived"}


# ── Mute ──


@router.post("/mute")
async def mute_chat(
    body: MuteRequest,
    partner_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_create_settings(db, current_user.id, partner_id, group_id)
    if body.hours is None:
        # Mute forever = far-future
        row.muted_until = datetime.now(timezone.utc) + timedelta(days=365 * 10)
    else:
        if body.hours <= 0:
            raise HTTPException(status_code=400, detail="hours must be positive")
        row.muted_until = datetime.now(timezone.utc) + timedelta(hours=body.hours)
    await db.commit()
    return {"detail": "Chat muted", "muted_until": row.muted_until.isoformat()}


@router.delete("/mute")
async def unmute_chat(
    partner_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_create_settings(db, current_user.id, partner_id, group_id)
    row.muted_until = None
    await db.commit()
    return {"detail": "Chat unmuted"}


# ── Folder assignment ──


@router.post("/folder")
async def assign_folder(
    body: FolderAssignRequest,
    partner_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.folder_id is not None:
        folder = await db.get(ChatFolder, body.folder_id)
        if not folder or folder.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Folder not found")

    row = await _get_or_create_settings(db, current_user.id, partner_id, group_id)
    row.folder_id = body.folder_id
    await db.commit()
    return {"detail": "Folder assigned", "folder_id": str(body.folder_id) if body.folder_id else None}
