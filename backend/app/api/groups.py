import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.group import Group, GroupMember, MemberRole
from app.models.message import Message
from app.models.user import User
from app.services.message_service import get_group_messages, save_message

router = APIRouter(prefix="/groups", tags=["groups"])


# ── Schemas ──

class GroupCreate(BaseModel):
    name: str
    description: str = ""
    member_ids: list[uuid.UUID] = []


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class GroupOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    avatar_url: str | None
    creator_id: uuid.UUID
    member_count: int = 0
    model_config = {"from_attributes": True}


class GroupMemberOut(BaseModel):
    user_id: uuid.UUID
    name: str
    phone: str
    avatar_url: str | None
    role: str
    is_online: bool
    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    content: str | None
    message_type: str
    media_url: str | None
    reply_to_id: uuid.UUID | None
    is_forwarded: bool
    is_pinned: bool
    created_at: str
    sender_name: str | None = None
    model_config = {"from_attributes": True}


# ── Helpers ──

async def _check_member(db: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID) -> GroupMember:
    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Not a group member")
    return member


async def _check_admin(db: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID) -> GroupMember:
    member = await _check_member(db, group_id, user_id)
    if member.role not in (MemberRole.OWNER, MemberRole.ADMIN):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return member


# ── Routes ──

@router.post("/", response_model=GroupOut)
async def create_group(
    body: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    group = Group(name=body.name, description=body.description, creator_id=current_user.id)
    db.add(group)
    await db.flush()

    # Add creator as owner
    db.add(GroupMember(group_id=group.id, user_id=current_user.id, role=MemberRole.OWNER))

    # Add initial members
    for uid in body.member_ids:
        if uid != current_user.id:
            db.add(GroupMember(group_id=group.id, user_id=uid, role=MemberRole.MEMBER))

    await db.commit()
    await db.refresh(group)

    return GroupOut(
        id=group.id, name=group.name, description=group.description,
        avatar_url=group.avatar_url, creator_id=group.creator_id,
        member_count=len(body.member_ids) + 1,
    )


@router.get("/", response_model=list[GroupOut])
async def list_my_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Group, func.count(GroupMember.id).label("mc"))
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == current_user.id)
        .group_by(Group.id)
    )
    groups = []
    for g, mc in result.all():
        groups.append(GroupOut(
            id=g.id, name=g.name, description=g.description,
            avatar_url=g.avatar_url, creator_id=g.creator_id, member_count=mc,
        ))
    return groups


@router.get("/{group_id}", response_model=GroupOut)
async def get_group(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_member(db, group_id, current_user.id)
    group = await db.get(Group, group_id)
    count_q = select(func.count()).where(GroupMember.group_id == group_id)
    count = (await db.execute(count_q)).scalar()
    return GroupOut(
        id=group.id, name=group.name, description=group.description,
        avatar_url=group.avatar_url, creator_id=group.creator_id, member_count=count,
    )


@router.patch("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: uuid.UUID,
    body: GroupUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_admin(db, group_id, current_user.id)
    group = await db.get(Group, group_id)
    if body.name is not None:
        group.name = body.name
    if body.description is not None:
        group.description = body.description
    await db.commit()
    await db.refresh(group)
    count = (await db.execute(select(func.count()).where(GroupMember.group_id == group_id))).scalar()
    return GroupOut(
        id=group.id, name=group.name, description=group.description,
        avatar_url=group.avatar_url, creator_id=group.creator_id, member_count=count,
    )


@router.get("/{group_id}/members", response_model=list[GroupMemberOut])
async def list_members(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_member(db, group_id, current_user.id)
    result = await db.execute(
        select(GroupMember, User)
        .join(User, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == group_id)
    )
    return [
        GroupMemberOut(
            user_id=u.id, name=u.name, phone=u.phone, avatar_url=u.avatar_url,
            role=gm.role.value, is_online=u.is_online,
        )
        for gm, u in result.all()
    ]


@router.post("/{group_id}/members/{user_id}")
async def add_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_admin(db, group_id, current_user.id)
    existing = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already a member")
    db.add(GroupMember(group_id=group_id, user_id=user_id, role=MemberRole.MEMBER))
    await db.commit()
    return {"detail": "Member added"}


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_admin(db, group_id, current_user.id)
    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == MemberRole.OWNER:
        raise HTTPException(status_code=403, detail="Cannot remove owner")
    await db.delete(member)
    await db.commit()
    return {"detail": "Member removed"}


@router.post("/{group_id}/leave")
async def leave_group(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member = await _check_member(db, group_id, current_user.id)
    if member.role == MemberRole.OWNER:
        raise HTTPException(status_code=400, detail="Owner must transfer ownership first")
    await db.delete(member)
    await db.commit()
    return {"detail": "Left group"}


@router.get("/{group_id}/messages")
async def get_messages(
    group_id: uuid.UUID,
    limit: int = 50,
    before: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_member(db, group_id, current_user.id)
    messages = await get_group_messages(db, group_id, current_user.id, limit, before)
    return messages


@router.get("/{group_id}/pinned")
async def get_pinned_messages(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_member(db, group_id, current_user.id)
    result = await db.execute(
        select(Message)
        .where(Message.group_id == group_id, Message.is_pinned == True)
        .order_by(Message.pinned_at.desc())
    )
    return result.scalars().all()
