import uuid
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

ALGORITHM = "HS256"

_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes)
    jti = str(uuid.uuid4())  # Unique token ID for revocation
    payload = {"sub": str(user_id), "exp": expire, "jti": jti}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.JWTError:
        return None


async def is_token_blacklisted(jti: str) -> bool:
    """C-2 FIX: Check if token is revoked."""
    try:
        r = await _get_redis()
        return await r.exists(f"blacklist:{jti}") > 0
    except Exception:
        return False


async def blacklist_token(jti: str, ttl_seconds: int = 604800) -> None:
    """Add token to blacklist. TTL = max token lifetime (7 days)."""
    try:
        r = await _get_redis()
        await r.setex(f"blacklist:{jti}", ttl_seconds, "1")
    except Exception:
        pass


async def blacklist_all_user_tokens(user_id: uuid.UUID) -> None:
    """Blacklist marker — forces re-validation on next request."""
    try:
        r = await _get_redis()
        await r.setex(f"user_logout:{user_id}", 604800, str(int(datetime.now(timezone.utc).timestamp())))
    except Exception:
        pass


async def is_user_logged_out_after(user_id: str, token_iat: int | None) -> bool:
    """Check if user logged out after this token was issued."""
    try:
        r = await _get_redis()
        logout_time = await r.get(f"user_logout:{user_id}")
        if logout_time and token_iat:
            return int(logout_time) > token_iat
    except Exception:
        pass
    return False


async def get_or_create_user(db: AsyncSession, phone: str) -> tuple[User, bool]:
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if user:
        return user, False
    user = User(phone=phone, name=phone)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, True
