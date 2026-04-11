import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, users, messages, contacts
from app.api import groups, channels, stories, calls, security, translation
from app.config import settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.websocket.handlers import websocket_endpoint

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="Nexly",
    description="Real-time messaging API — Chat, Groups, Channels, Calls",
    version="0.2.0",
)

# Rate limiting
app.add_middleware(RateLimitMiddleware, requests_per_minute=120, burst=30)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes — Phase 1 (MVP)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(contacts.router, prefix="/api/v1")

# API routes — Phase 2/3 (Social)
app.include_router(groups.router, prefix="/api/v1")
app.include_router(channels.router, prefix="/api/v1")
app.include_router(stories.router, prefix="/api/v1")

# API routes — Phase 4 (Calls)
app.include_router(calls.router, prefix="/api/v1")

# API routes — Phase 6 (Security)
app.include_router(security.router, prefix="/api/v1")

# API routes — Translation
app.include_router(translation.router, prefix="/api/v1")

# WebSocket
app.websocket("/ws")(websocket_endpoint)

# Serve media
os.makedirs(settings.media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


@app.get("/health")
async def health():
    return {"status": "ok", "app": "Nexly", "version": "0.3.0"}
