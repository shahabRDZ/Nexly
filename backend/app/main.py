import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, users, messages, contacts
from app.api import groups, channels, stories, calls, security, translation
from app.api import reactions, polls, moderation, ai, enhanced_messages, admin
from app.config import settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.websocket.handlers import websocket_endpoint

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="Nexly",
    description="Real-time messaging platform with AI, translation, calls, and more",
    version="1.0.0",
)

app.add_middleware(RateLimitMiddleware, requests_per_minute=120, burst=30)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Core
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(contacts.router, prefix="/api/v1")

# Social
app.include_router(groups.router, prefix="/api/v1")
app.include_router(channels.router, prefix="/api/v1")
app.include_router(stories.router, prefix="/api/v1")

# Calls
app.include_router(calls.router, prefix="/api/v1")

# Security
app.include_router(security.router, prefix="/api/v1")

# Translation
app.include_router(translation.router, prefix="/api/v1")

# Reactions, Polls, Moderation
app.include_router(reactions.router, prefix="/api/v1")
app.include_router(polls.router, prefix="/api/v1")
app.include_router(moderation.router, prefix="/api/v1")

# AI Features
app.include_router(ai.router, prefix="/api/v1")

# Enhanced Messages (edit, search, disappearing, location, sticker)
app.include_router(enhanced_messages.router, prefix="/api/v1")

# Admin & Analytics
app.include_router(admin.router, prefix="/api/v1")

# WebSocket
app.websocket("/ws")(websocket_endpoint)

# Media
os.makedirs(settings.media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


@app.get("/health")
async def health():
    return {"status": "ok", "app": "Nexly", "version": "1.0.0"}
