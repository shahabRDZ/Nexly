import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.block import Session
from app.schemas.auth import PhoneRequest, OTPVerify, TokenResponse
from app.services.otp_service import generate_otp, verify_otp
from app.services.auth_service import get_or_create_user, create_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-otp")
async def send_otp(body: PhoneRequest):
    """Send OTP to the given phone number."""
    code = await generate_otp(body.phone)
    # C-1 FIX: Only return debug code in dev mode
    response = {"message": "OTP sent"}
    if settings.sms_provider == "console":
        response["debug_code"] = code
    return response


@router.post("/verify-otp", response_model=TokenResponse)
async def verify(body: OTPVerify, request: Request, db: AsyncSession = Depends(get_db)):
    """Verify OTP and return JWT token."""
    valid = await verify_otp(body.phone, body.code)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    user, is_new = await get_or_create_user(db, body.phone)
    token = create_access_token(user.id)

    # Track session
    device = request.headers.get("user-agent", "Unknown")[:200]
    ip = request.client.host if request.client else None
    db.add(Session(user_id=user.id, device_name=device, ip_address=ip))
    await db.commit()

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        is_new_user=is_new,
    )
