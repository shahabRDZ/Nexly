"""C-1 FIX: Redis-based rate limiter — works across multiple workers/containers."""
import time

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

import redis.asyncio as aioredis
from app.config import settings

_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60, burst: int = 20):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.burst = burst

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        try:
            r = await _get_redis()
            now = int(time.time())
            minute_key = f"rl:{client_ip}:{now // 60}"
            second_key = f"rl_burst:{client_ip}:{now // 2}"

            # Per-minute limit
            pipe = r.pipeline()
            pipe.incr(minute_key)
            pipe.expire(minute_key, 120)
            pipe.incr(second_key)
            pipe.expire(second_key, 5)
            results = await pipe.execute()

            minute_count = results[0]
            burst_count = results[2]

            if minute_count > self.rpm:
                raise HTTPException(status_code=429, detail=f"Rate limit exceeded ({self.rpm}/min)")
            if burst_count > self.burst:
                raise HTTPException(status_code=429, detail="Too many requests, slow down")

        except HTTPException:
            raise
        except Exception:
            pass  # If Redis is down, allow request through

        return await call_next(request)
