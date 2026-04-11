import pyotp
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/security", tags=["security"])


class Enable2FAResponse(BaseModel):
    secret: str
    otpauth_url: str


class Verify2FA(BaseModel):
    code: str


@router.post("/2fa/enable", response_model=Enable2FAResponse)
async def enable_2fa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.two_fa_enabled:
        raise HTTPException(status_code=400, detail="2FA already enabled")

    secret = pyotp.random_base32()
    current_user.totp_secret = secret
    await db.commit()

    totp = pyotp.TOTP(secret)
    url = totp.provisioning_uri(name=current_user.phone, issuer_name="Nexly")
    return Enable2FAResponse(secret=secret, otpauth_url=url)


@router.post("/2fa/verify")
async def verify_2fa(
    body: Verify2FA,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA not set up. Call /enable first")

    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(body.code):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")

    current_user.two_fa_enabled = True
    await db.commit()
    return {"detail": "2FA enabled successfully"}


@router.post("/2fa/disable")
async def disable_2fa(
    body: Verify2FA,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.two_fa_enabled:
        raise HTTPException(status_code=400, detail="2FA not enabled")

    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(body.code):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")

    current_user.totp_secret = None
    current_user.two_fa_enabled = False
    await db.commit()
    return {"detail": "2FA disabled"}


# ── E2E Key Exchange ──


class PublicKeyUpload(BaseModel):
    public_key: str


@router.post("/keys/upload")
async def upload_public_key(
    body: PublicKeyUpload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.public_key = body.public_key
    await db.commit()
    return {"detail": "Public key uploaded"}


@router.get("/keys/{user_id}")
async def get_public_key(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.public_key:
        raise HTTPException(status_code=404, detail="Public key not found")
    return {"user_id": str(user.id), "public_key": user.public_key}
