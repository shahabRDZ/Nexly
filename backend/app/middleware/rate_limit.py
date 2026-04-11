import time
from collections import defaultdict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter. Use Redis in production for multi-instance."""

    def __init__(self, app, requests_per_minute: int = 60, burst: int = 20):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.burst = burst
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limit for health and docs
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = 60.0

        # Clean old entries
        bucket = self._buckets[client_ip]
        self._buckets[client_ip] = [t for t in bucket if now - t < window]
        bucket = self._buckets[client_ip]

        if len(bucket) >= self.rpm:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {self.rpm} requests per minute.",
            )

        # Burst check (10 requests in 2 seconds)
        recent = [t for t in bucket if now - t < 2.0]
        if len(recent) >= self.burst:
            raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

        bucket.append(now)
        return await call_next(request)
