import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.message import Message
from app.models.user import User
from app.services.translation_service import (
    get_supported_languages,
    translate,
    detect_language,
)

router = APIRouter(prefix="/translation", tags=["translation"])


class SetLanguageRequest(BaseModel):
    language: str


class TranslateRequest(BaseModel):
    text: str
    source: str = "auto"
    target: str = "en"


class TranslateResponse(BaseModel):
    translated_text: str
    source_language: str
    target_language: str
    confidence: float


@router.get("/languages")
async def list_languages():
    """Get all supported languages."""
    langs = get_supported_languages()
    return [{"code": k, "name": v} for k, v in langs.items()]


@router.post("/set-language")
async def set_preferred_language(
    body: SetLanguageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set user's preferred language. All incoming messages will be translated to this language."""
    supported = get_supported_languages()
    if body.language not in supported:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unsupported language. Supported: {list(supported.keys())}")

    current_user.preferred_language = body.language
    await db.commit()
    return {"detail": f"Language set to {supported[body.language]}", "language": body.language}


@router.post("/translate", response_model=TranslateResponse)
async def translate_text(
    body: TranslateRequest,
    _: User = Depends(get_current_user),
):
    """Manual translation endpoint for testing."""
    source = body.source
    if source == "auto":
        source = await detect_language(body.text)

    result = await translate(body.text, source, body.target)
    return TranslateResponse(
        translated_text=result.translated_text,
        source_language=result.source_language,
        target_language=result.target_language,
        confidence=result.confidence,
    )


@router.get("/message/{message_id}/original")
async def get_original_message(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the original (untranslated) content of a message."""
    msg = await db.get(Message, message_id)
    if not msg:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Message not found")

    return {
        "message_id": str(msg.id),
        "original_content": msg.original_content or msg.content,
        "translated_content": msg.content,
        "source_language": msg.source_language,
        "was_translated": msg.translated,
    }
