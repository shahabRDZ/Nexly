import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import PhoneRequest, OTPVerify, TokenResponse
from app.services.otp_service import generate_otp, verify_otp
from app.services.auth_service import get_or_create_user, create_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-otp")
async def send_otp(body: PhoneRequest):
    """Send OTP to the given phone number."""
    code = await generate_otp(body.phone)
    # In production, never return the code — it's sent via SMS.
    # We return it here for development convenience.
    return {"message": "OTP sent", "debug_code": code}


@router.post("/verify-otp", response_model=TokenResponse)
async def verify(body: OTPVerify, db: AsyncSession = Depends(get_db)):
    """Verify OTP and return JWT token."""
    valid = await verify_otp(body.phone, body.code)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    user, is_new = await get_or_create_user(db, body.phone)
    token = create_access_token(user.id)

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        is_new_user=is_new,
    )
