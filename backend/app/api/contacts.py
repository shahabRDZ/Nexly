import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.contact import Contact
from app.models.user import User
from app.schemas.user import UserProfile

router = APIRouter(prefix="/contacts", tags=["contacts"])


class SyncContactsRequest(BaseModel):
    phone_numbers: list[str]


class SyncContactsResponse(BaseModel):
    registered: list[UserProfile]
    not_found: list[str]


@router.post("/sync", response_model=SyncContactsResponse)
async def sync_contacts(
    body: SyncContactsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check which phone contacts are registered on Nexly."""
    result = await db.execute(
        select(User).where(User.phone.in_(body.phone_numbers), User.id != current_user.id)
    )
    registered_users = result.scalars().all()
    registered_phones = {u.phone for u in registered_users}

    # Auto-add discovered users as contacts
    for user in registered_users:
        existing = await db.execute(
            select(Contact).where(
                and_(Contact.owner_id == current_user.id, Contact.contact_id == user.id)
            )
        )
        if not existing.scalar_one_or_none():
            db.add(Contact(owner_id=current_user.id, contact_id=user.id))
    await db.commit()

    return SyncContactsResponse(
        registered=[UserProfile.model_validate(u) for u in registered_users],
        not_found=[p for p in body.phone_numbers if p not in registered_phones],
    )


@router.get("/", response_model=list[UserProfile])
async def get_contacts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all contacts for the current user."""
    result = await db.execute(
        select(User)
        .join(Contact, Contact.contact_id == User.id)
        .where(Contact.owner_id == current_user.id)
    )
    return result.scalars().all()


@router.delete("/{contact_user_id}")
async def remove_contact(
    contact_user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Contact).where(
            and_(Contact.owner_id == current_user.id, Contact.contact_id == contact_user_id)
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    await db.delete(contact)
    await db.commit()
    return {"detail": "Contact removed"}
