"""
Real-time translation service with Redis caching.

Architecture:
  1. Detect source language (or use sender's preferred_language)
  2. Check Redis cache for existing translation
  3. If miss → call translation backend (LibreTranslate / Google / DeepL)
  4. Cache result with TTL
  5. Return translated text + metadata

The service is designed to be INVISIBLE to users — translation happens
automatically before message delivery.
"""

import hashlib
import json
import logging
from typing import NamedTuple

import httpx
import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

# ── Supported Languages ──

SUPPORTED_LANGUAGES = {
    "en": "English",
    "fa": "فارسی (Persian)",
    "ar": "العربية (Arabic)",
    "es": "Español (Spanish)",
    "fr": "Français (French)",
    "de": "Deutsch (German)",
    "it": "Italiano (Italian)",
    "pt": "Português (Portuguese)",
    "ru": "Русский (Russian)",
    "zh": "中文 (Chinese)",
    "ja": "日本語 (Japanese)",
    "ko": "한국어 (Korean)",
    "tr": "Türkçe (Turkish)",
    "hi": "हिन्दी (Hindi)",
    "uk": "Українська (Ukrainian)",
    "nl": "Nederlands (Dutch)",
    "pl": "Polski (Polish)",
    "sv": "Svenska (Swedish)",
    "da": "Dansk (Danish)",
    "fi": "Suomi (Finnish)",
}


class TranslationResult(NamedTuple):
    translated_text: str
    source_language: str
    target_language: str
    confidence: float  # 0.0 to 1.0
    cached: bool


# ── Redis Cache ──

_redis: redis.Redis | None = None
CACHE_TTL = 86400 * 7  # 7 days


async def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _cache_key(text: str, source: str, target: str) -> str:
    text_hash = hashlib.md5(text.encode()).hexdigest()
    return f"tr:{source}:{target}:{text_hash}"


async def _get_cached(text: str, source: str, target: str) -> dict | None:
    r = await _get_redis()
    key = _cache_key(text, source, target)
    cached = await r.get(key)
    if cached:
        return json.loads(cached)
    return None


async def _set_cached(text: str, source: str, target: str, result: dict) -> None:
    r = await _get_redis()
    key = _cache_key(text, source, target)
    await r.setex(key, CACHE_TTL, json.dumps(result))


# ── Translation Backends ──


async def _translate_libretranslate(text: str, source: str, target: str) -> dict:
    """Translate using LibreTranslate (self-hosted, free)."""
    url = getattr(settings, "libretranslate_url", "http://libretranslate:5000")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{url}/translate", json={
            "q": text,
            "source": source,
            "target": target,
            "format": "text",
        })
        resp.raise_for_status()
        data = resp.json()
        return {
            "translated_text": data["translatedText"],
            "confidence": data.get("confidence", 0.85),
        }


async def _detect_language_libretranslate(text: str) -> str:
    """Detect language using LibreTranslate."""
    url = getattr(settings, "libretranslate_url", "http://libretranslate:5000")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{url}/detect", json={"q": text})
            resp.raise_for_status()
            data = resp.json()
            if data and len(data) > 0:
                return data[0]["language"]
    except Exception as e:
        logger.warning("Language detection failed: %s", e)
    return "auto"


# ── Public API ──


async def detect_language(text: str) -> str:
    """Detect the language of the given text."""
    if not text or len(text.strip()) < 2:
        return "en"
    return await _detect_language_libretranslate(text)


async def translate(
    text: str,
    source_lang: str,
    target_lang: str,
) -> TranslationResult:
    """
    Translate text from source_lang to target_lang.
    Uses Redis cache to avoid redundant API calls.
    Returns TranslationResult with translated text and metadata.
    """
    # No translation needed if same language
    if source_lang == target_lang:
        return TranslationResult(
            translated_text=text,
            source_language=source_lang,
            target_language=target_lang,
            confidence=1.0,
            cached=False,
        )

    # Skip translation for very short text, emojis, numbers
    if not text or len(text.strip()) < 2 or _is_emoji_or_number(text):
        return TranslationResult(
            translated_text=text,
            source_language=source_lang,
            target_language=target_lang,
            confidence=1.0,
            cached=False,
        )

    # Check cache
    cached = await _get_cached(text, source_lang, target_lang)
    if cached:
        return TranslationResult(
            translated_text=cached["translated_text"],
            source_language=source_lang,
            target_language=target_lang,
            confidence=cached.get("confidence", 0.85),
            cached=True,
        )

    # Call translation backend
    try:
        result = await _translate_libretranslate(text, source_lang, target_lang)

        # Cache the result
        await _set_cached(text, source_lang, target_lang, result)

        return TranslationResult(
            translated_text=result["translated_text"],
            source_language=source_lang,
            target_language=target_lang,
            confidence=result.get("confidence", 0.85),
            cached=False,
        )

    except Exception as e:
        logger.error("Translation failed (%s→%s): %s", source_lang, target_lang, e)
        # Fallback: return original text
        return TranslationResult(
            translated_text=text,
            source_language=source_lang,
            target_language=target_lang,
            confidence=0.0,
            cached=False,
        )


async def translate_for_user(
    text: str,
    sender_lang: str,
    receiver_lang: str,
) -> TranslationResult:
    """
    High-level function: translate a message from sender's language
    to receiver's language. Handles auto-detection if sender_lang is 'auto'.
    """
    if sender_lang == "auto":
        sender_lang = await detect_language(text)

    return await translate(text, sender_lang, receiver_lang)


def _is_emoji_or_number(text: str) -> bool:
    """Check if text is only emojis, numbers, or punctuation."""
    stripped = text.strip()
    for char in stripped:
        if char.isalpha():
            return False
    return True


def get_supported_languages() -> dict[str, str]:
    """Return dict of supported language codes and names."""
    return SUPPORTED_LANGUAGES.copy()
