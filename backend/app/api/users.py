import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.user import UserProfile, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserProfile)
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.name is not None:
        current_user.name = body.name
    if body.status_text is not None:
        current_user.status_text = body.status_text
    if body.preferred_language is not None:
        current_user.preferred_language = body.preferred_language
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/me/avatar", response_model=UserProfile)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WebP images allowed")

    avatar_dir = os.path.join(settings.media_dir, "avatars")
    os.makedirs(avatar_dir, exist_ok=True)

    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "jpg"
    filename = f"{current_user.id}.{ext}"
    filepath = os.path.join(avatar_dir, filename)

    async with aiofiles.open(filepath, "wb") as f:
        content = await file.read()
        await f.write(content)

    current_user.avatar_url = f"/media/avatars/{filename}"
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/{user_id}", response_model=UserProfile)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/search/", response_model=list[UserProfile])
async def search_users(
    q: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Search users by phone or name."""
    result = await db.execute(
        select(User)
        .where(or_(User.phone.ilike(f"%{q}%"), User.name.ilike(f"%{q}%")))
        .limit(20)
    )
    return result.scalars().all()
