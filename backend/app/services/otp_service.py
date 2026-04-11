import secrets
import logging

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _otp_key(phone: str) -> str:
    return f"otp:{phone}"


async def generate_otp(phone: str) -> str:
    """Generate a 6-digit OTP and store in Redis with expiry."""
    code = f"{secrets.randbelow(900000) + 100000}"
    r = await get_redis()
    await r.setex(_otp_key(phone), settings.otp_expiry_seconds, code)

    # In dev mode, log the OTP to console
    if settings.sms_provider == "console":
        logger.info("OTP for %s: %s", phone, code)
    else:
        # TODO: integrate real SMS provider (Twilio, Kavenegar, etc.)
        pass

    return code


async def verify_otp(phone: str, code: str) -> bool:
    """Verify OTP and delete it on success."""
    r = await get_redis()
    stored = await r.get(_otp_key(phone))
    if stored and stored == code:
        await r.delete(_otp_key(phone))
        return True
    return False
