import os
import uuid
from datetime import datetime, timedelta, timezone

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.story import Story, StoryView, StoryType
from app.models.contact import Contact
from app.models.user import User

router = APIRouter(prefix="/stories", tags=["stories"])


class TextStoryCreate(BaseModel):
    text_content: str
    bg_color: str = "#6C5CE7"


class StoryOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    story_type: str
    media_url: str | None
    text_content: str | None
    bg_color: str | None
    view_count: int
    created_at: str
    expires_at: str
    is_viewed: bool = False
    model_config = {"from_attributes": True}


class StoryUserGroup(BaseModel):
    user_id: uuid.UUID
    name: str
    avatar_url: str | None
    stories: list[StoryOut]
    has_unviewed: bool


@router.post("/text", response_model=StoryOut)
async def create_text_story(
    body: TextStoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    story = Story(
        user_id=current_user.id,
        story_type=StoryType.TEXT,
        text_content=body.text_content,
        bg_color=body.bg_color,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return _story_out(story)


@router.post("/media", response_model=StoryOut)
async def create_media_story(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ct = file.content_type or ""
    story_type = StoryType.VIDEO if "video" in ct else StoryType.IMAGE

    # M-16 + L-6 FIX: Size limit + extension whitelist
    SAFE_EXT = {"jpg", "jpeg", "png", "gif", "webp", "mp4", "webm", "mov"}
    story_dir = os.path.join(settings.media_dir, "stories")
    os.makedirs(story_dir, exist_ok=True)
    raw_ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "jpg"
    ext = raw_ext if raw_ext in SAFE_EXT else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(story_dir, filename)
    content = await file.read()
    if len(content) > settings.max_upload_size:
        raise HTTPException(status_code=413, detail="File too large")
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(content)

    story = Story(
        user_id=current_user.id,
        story_type=story_type,
        media_url=f"/media/stories/{filename}",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return _story_out(story)


@router.get("/feed", response_model=list[StoryUserGroup])
async def get_story_feed(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get stories from contacts, grouped by user."""
    now = datetime.now(timezone.utc)

    # Get contacts
    contacts_q = select(Contact.contact_id).where(Contact.owner_id == current_user.id)
    contact_result = await db.execute(contacts_q)
    contact_ids = [row[0] for row in contact_result.all()]
    contact_ids.append(current_user.id)  # Include own stories

    # Get active stories
    stories_q = (
        select(Story)
        .where(Story.user_id.in_(contact_ids), Story.expires_at > now)
        .order_by(Story.created_at.asc())
    )
    result = await db.execute(stories_q)
    stories = result.scalars().all()

    # Get viewed stories
    viewed_q = select(StoryView.story_id).where(StoryView.user_id == current_user.id)
    viewed_result = await db.execute(viewed_q)
    viewed_ids = {row[0] for row in viewed_result.all()}

    # Group by user
    user_stories: dict[uuid.UUID, list] = {}
    for s in stories:
        user_stories.setdefault(s.user_id, []).append(s)

    # Batch fetch all users at once instead of one query per user
    user_ids = list(user_stories.keys())
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    groups = []
    for uid, sts in user_stories.items():
        user = users_map.get(uid)
        if not user:
            continue
        story_outs = [_story_out(s, s.id in viewed_ids) for s in sts]
        groups.append(StoryUserGroup(
            user_id=uid,
            name=user.name,
            avatar_url=user.avatar_url,
            stories=story_outs,
            has_unviewed=any(not so.is_viewed for so in story_outs),
        ))

    # Own stories first, then unviewed first
    groups.sort(key=lambda g: (g.user_id != current_user.id, not g.has_unviewed))
    return groups


@router.post("/{story_id}/view")
async def view_story(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    story = await db.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    existing = await db.execute(
        select(StoryView).where(StoryView.story_id == story_id, StoryView.user_id == current_user.id)
    )
    if not existing.scalar_one_or_none():
        db.add(StoryView(story_id=story_id, user_id=current_user.id))
        story.view_count += 1
        await db.commit()
    return {"detail": "Viewed"}


@router.get("/{story_id}/viewers")
async def get_story_viewers(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    story = await db.get(Story, story_id)
    if not story or story.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Can only view own story viewers")

    result = await db.execute(
        select(StoryView, User)
        .join(User, StoryView.user_id == User.id)
        .where(StoryView.story_id == story_id)
        .order_by(StoryView.viewed_at.desc())
    )
    return [
        {"user_id": str(u.id), "name": u.name, "avatar_url": u.avatar_url, "viewed_at": sv.viewed_at.isoformat()}
        for sv, u in result.all()
    ]


@router.delete("/{story_id}")
async def delete_story(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    story = await db.get(Story, story_id)
    if not story or story.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your story")
    await db.delete(story)
    await db.commit()
    return {"detail": "Story deleted"}


def _story_out(story: Story, is_viewed: bool = False) -> StoryOut:
    return StoryOut(
        id=story.id, user_id=story.user_id, story_type=story.story_type.value,
        media_url=story.media_url, text_content=story.text_content, bg_color=story.bg_color,
        view_count=story.view_count, created_at=story.created_at.isoformat(),
        expires_at=story.expires_at.isoformat(), is_viewed=is_viewed,
    )
