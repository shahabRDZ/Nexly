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


def _otp_rate_key(phone: str) -> str:
    return f"otp_rate:{phone}"


async def generate_otp(phone: str) -> str:
    """Generate 6-digit OTP with per-phone rate limiting (C-7 FIX)."""
    r = await get_redis()

    # C-7: Per-phone rate limit — max 5 OTPs per 10 minutes
    rate_key = _otp_rate_key(phone)
    rate_count = await r.incr(rate_key)
    if rate_count == 1:
        await r.expire(rate_key, 600)  # 10 min window
    if rate_count > 5:
        raise ValueError("Too many OTP requests. Try again in a few minutes.")

    code = f"{secrets.randbelow(900000) + 100000}"
    await r.setex(_otp_key(phone), settings.otp_expiry_seconds, code)

    if settings.sms_provider == "console":
        logger.info("OTP for %s: %s", phone, code)

    return code


async def verify_otp(phone: str, code: str) -> bool:
    r = await get_redis()
    stored = await r.get(_otp_key(phone))
    if stored and stored == code:
        await r.delete(_otp_key(phone))
        return True
    return False
