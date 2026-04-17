# Nexly

A next-generation messaging platform built with **FastAPI** and **React (TypeScript)**, featuring real-time communication, AI-powered features, translation, voice rooms, and more.

## Features

- **Real-time Messaging** — WebSocket-based instant messaging with read receipts and typing indicators
- **Groups & Channels** — Create group chats and broadcast channels with admin controls
- **Voice Rooms** — Live voice communication rooms
- **AI Integration** — AI-powered message assistance and smart features
- **Live Translation** — Real-time message translation powered by LibreTranslate (14+ languages)
- **Stories** — Share ephemeral content with contacts
- **Polls & Reactions** — Interactive message engagement
- **Scheduled Messages** — Send messages at a specified time
- **Moderation Tools** — Content moderation and user management
- **Admin Dashboard** — Full administrative control panel
- **Security** — Rate limiting, security headers, CORS, and authentication

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python, FastAPI, SQLAlchemy, Alembic |
| **Frontend** | React, TypeScript, Vite |
| **Database** | PostgreSQL 16 |
| **Cache** | Redis 7 |
| **Translation** | LibreTranslate (self-hosted) |
| **Infrastructure** | Docker, Docker Compose |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/shahabRDZ/Nexly.git
cd Nexly

# Start all services
docker-compose up -d

# Backend API: http://localhost:8000
# Frontend:   http://localhost:5173
# API Docs:   http://localhost:8000/docs
```

## API Endpoints

| Module | Prefix | Description |
|--------|--------|-------------|
| Auth | `/api/v1/auth` | Registration, login, token management |
| Users | `/api/v1/users` | User profiles and settings |
| Messages | `/api/v1/messages` | Send, edit, delete messages |
| Groups | `/api/v1/groups` | Group management |
| Channels | `/api/v1/channels` | Broadcast channels |
| Stories | `/api/v1/stories` | Ephemeral content |
| Calls | `/api/v1/calls` | Voice/video calls |
| Translation | `/api/v1/translation` | Message translation |
| AI | `/api/v1/ai` | AI-powered features |
| Voice Rooms | `/api/v1/voice-rooms` | Live voice rooms |
| Admin | `/api/v1/admin` | Administration panel |

## Architecture

```
nexly/
├── backend/
│   ├── app/
│   │   ├── api/          # Route handlers
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   ├── middleware/   # Rate limiting, etc.
│   │   ├── websocket/    # WebSocket handlers
│   │   └── utils/        # Helpers
│   ├── alembic/          # Database migrations
│   └── Dockerfile
├── frontend/
│   └── src/              # React + TypeScript
└── docker-compose.yml
```

## Environment Variables

Copy `.env.example` and configure:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Auto-configured via Docker |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `SECRET_KEY` | JWT signing key | Auto-generated if not set |
| `ADMIN_PHONES` | Admin phone numbers | — |
| `TRANSLATION_ENABLED` | Enable translation | `true` |
| `ALLOWED_ORIGINS` | CORS origins | `*` |

## License

MIT

---

## Join the Discussion

Have ideas or experience to share? Check out our open discussions:

- [Real-time architecture: WebSocket vs SSE vs message broker](https://github.com/shahabRDZ/Nexly/discussions/33)
- [Translation strategy: API vs local model vs caching](https://github.com/shahabRDZ/Nexly/discussions/34)

We'd love to hear your thoughts!