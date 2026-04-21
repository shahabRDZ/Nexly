import logging
import os

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, users, messages, contacts
from app.api import groups, channels, stories, calls, security, translation
from app.api import reactions, polls, moderation, ai, enhanced_messages, admin
from app.api import voice_rooms, schedule, innovative
from app.api import chat_settings, saved_messages
from app.config import settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.websocket.handlers import websocket_endpoint

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="Nexly",
    description="Next-gen messaging platform with AI, translation, voice rooms, and more",
    version="2.1.0",
)

# Rate limiting
app.add_middleware(RateLimitMiddleware, requests_per_minute=120, burst=30)

# C-5 FIX: Proper CORS — use configured origins
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# L-12 FIX: Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


# Core
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(contacts.router, prefix="/api/v1")

# Social
app.include_router(groups.router, prefix="/api/v1")
app.include_router(channels.router, prefix="/api/v1")
app.include_router(stories.router, prefix="/api/v1")
app.include_router(calls.router, prefix="/api/v1")

# Intelligence
app.include_router(translation.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")

# Engagement
app.include_router(reactions.router, prefix="/api/v1")
app.include_router(polls.router, prefix="/api/v1")
app.include_router(enhanced_messages.router, prefix="/api/v1")

# Moderation & Security
app.include_router(security.router, prefix="/api/v1")
app.include_router(moderation.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")

# Innovative Features
app.include_router(voice_rooms.router, prefix="/api/v1")
app.include_router(schedule.router, prefix="/api/v1")
app.include_router(innovative.router, prefix="/api/v1")

# Chat organization (pin, archive, mute, folders, saved messages)
app.include_router(chat_settings.router, prefix="/api/v1")
app.include_router(saved_messages.router, prefix="/api/v1")

# WebSocket
app.websocket("/ws")(websocket_endpoint)

# Media
os.makedirs(settings.media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


@app.on_event("startup")
async def startup():
    from app.services.background_tasks import start_background_tasks
    start_background_tasks()


@app.on_event("shutdown")
async def shutdown():
    from app.services.background_tasks import stop_background_tasks
    stop_background_tasks()


@app.get("/health")
async def health():
    return {"status": "ok", "app": "Nexly", "version": "2.2.0"}
