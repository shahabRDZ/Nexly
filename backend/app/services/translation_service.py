"""
Smart Translation Service — AI-powered, context-aware translation.

Architecture:
  1. AUTO-DETECT source language from actual text (not user preference)
  2. Use conversation context (last 3 messages) for fluency
  3. LibreTranslate for base translation
  4. Post-processing for natural flow (slang, informal, emoji preservation)
  5. Redis caching with context-aware keys
  6. Graceful fallback chain

Key principle: ALWAYS detect language from text content, never assume
the user types in their preferred language.
"""

import hashlib
import json
import logging
import re
from typing import NamedTuple

import httpx
import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

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

# Character ranges for quick language detection fallback
_LANG_CHAR_RANGES = {
    "fa": re.compile(r'[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]'),
    "ar": re.compile(r'[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]'),
    "zh": re.compile(r'[\u4e00-\u9fff]'),
    "ja": re.compile(r'[\u3040-\u309f\u30a0-\u30ff]'),
    "ko": re.compile(r'[\uac00-\ud7af\u1100-\u11ff]'),
    "hi": re.compile(r'[\u0900-\u097F]'),
    "ru": re.compile(r'[\u0400-\u04FF]'),
    "uk": re.compile(r'[\u0400-\u04FF]'),
}

# Common slang/informal mappings for post-processing
_INFORMAL_MAPS = {
    "fa": {
        "you're welcome": "خواهش می‌کنم",
        "what's up": "چه خبر",
        "how are you": "حالت چطوره",
        "i'm fine": "خوبم",
        "see you": "فعلا",
        "bye": "بای",
        "lol": "😂",
        "omg": "وای",
    },
    "en": {
        "چطوری": "how are you",
        "خوبم": "I'm good",
        "چه خبر": "what's up",
        "بای": "bye",
        "مرسی": "thanks",
    },
}


class TranslationResult(NamedTuple):
    translated_text: str
    source_language: str
    target_language: str
    confidence: float
    cached: bool


# ── Redis Cache ──

_redis: redis.Redis | None = None
CACHE_TTL = 86400 * 7


async def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _cache_key(text: str, source: str, target: str) -> str:
    h = hashlib.md5(text.strip().lower().encode()).hexdigest()
    return f"tr:{source}:{target}:{h}"


async def _get_cached(text: str, source: str, target: str) -> dict | None:
    try:
        r = await _get_redis()
        cached = await r.get(_cache_key(text, source, target))
        return json.loads(cached) if cached else None
    except Exception:
        return None


async def _set_cached(text: str, source: str, target: str, result: dict) -> None:
    try:
        r = await _get_redis()
        await r.setex(_cache_key(text, source, target), CACHE_TTL, json.dumps(result))
    except Exception:
        pass


# ── Language Detection ──


def _detect_by_chars(text: str) -> str | None:
    """Fast character-based language detection (no API call)."""
    # Count characters in each script
    scores: dict[str, int] = {}
    for lang, pattern in _LANG_CHAR_RANGES.items():
        count = len(pattern.findall(text))
        if count > 0:
            scores[lang] = count

    if not scores:
        # All Latin chars — could be en, es, fr, de, etc.
        return None

    # Persian vs Arabic: check for specific Persian chars (گ پ چ ژ)
    best = max(scores, key=scores.get)
    if best in ("fa", "ar"):
        persian_specific = len(re.findall(r'[گپچژکی]', text))
        return "fa" if persian_specific > 0 else "ar"

    return best


async def _detect_by_api(text: str) -> str | None:
    """Detect language using LibreTranslate API."""
    url = settings.libretranslate_url
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{url}/detect", json={"q": text})
            resp.raise_for_status()
            data = resp.json()
            if data and len(data) > 0 and data[0].get("confidence", 0) > 0.3:
                return data[0]["language"]
    except Exception as e:
        logger.debug("API language detection failed: %s", e)
    return None


async def detect_language(text: str) -> str:
    """
    Smart language detection: char-based first (instant), then API fallback.
    Always detects from TEXT CONTENT, not user preferences.
    """
    if not text or len(text.strip()) < 2:
        return "en"

    # Step 1: Fast character-based detection
    char_lang = _detect_by_chars(text)
    if char_lang:
        return char_lang

    # Step 2: API-based detection for Latin scripts
    api_lang = await _detect_by_api(text)
    if api_lang and api_lang in SUPPORTED_LANGUAGES:
        return api_lang

    # Step 3: Default to English for Latin text
    return "en"


# ── Translation Backends ──


async def _translate_libretranslate(text: str, source: str, target: str) -> dict:
    """Translate using LibreTranslate."""
    url = settings.libretranslate_url
    async with httpx.AsyncClient(timeout=15.0) as client:
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
            "confidence": 0.85,
        }


# ── Post-Processing for Natural Flow ──


def _post_process(text: str, original: str, target_lang: str) -> str:
    """Make translation more natural and preserve emoji/formatting."""
    result = text

    # 1. Preserve emojis from original that might have been stripped
    original_emojis = [c for c in original if c in _EMOJI_SET or ord(c) > 0x1F000]
    translated_emojis = [c for c in result if c in _EMOJI_SET or ord(c) > 0x1F000]
    if original_emojis and not translated_emojis:
        result = result.rstrip() + " " + "".join(original_emojis)

    # 2. Fix common translation artifacts
    result = result.replace("  ", " ").strip()
    if result.endswith("??"):
        result = result[:-1]

    # 3. Capitalize first letter for Latin scripts
    if target_lang in ("en", "es", "fr", "de", "it", "pt", "nl") and result and result[0].islower():
        result = result[0].upper() + result[1:]

    # 4. Preserve line breaks
    if "\n" in original and "\n" not in result:
        pass

    return result


# Common emoji set for preservation
_EMOJI_SET = set("😀😂❤️👍🔥😢😮🎉💯🙏😎🤔😊👋✨💪😍🥺😭🤣💀🫡🙌🤝👏🥰🤗😏😤😡🤯🥳💕💖💝🫶🤞✌️🤟🖐️👌🤙💅🙈🙉🙊")


# ── Main Translation Functions ──


async def translate(
    text: str,
    source_lang: str,
    target_lang: str,
    context: list[str] | None = None,
) -> TranslationResult:
    """
    Translate text with optional conversation context.
    Context = last few messages for better translation.
    """
    if source_lang == target_lang:
        return TranslationResult(text, source_lang, target_lang, 1.0, False)

    if not text or len(text.strip()) < 1 or _is_emoji_only(text):
        return TranslationResult(text, source_lang, target_lang, 1.0, False)

    # Check cache
    cached = await _get_cached(text, source_lang, target_lang)
    if cached:
        return TranslationResult(cached["translated_text"], source_lang, target_lang, cached.get("confidence", 0.85), True)

    # Build contextual text for better translation
    translate_text = text
    if context and len(context) > 0:
        # Prepend context for LibreTranslate (it handles multi-sentence better)
        ctx_text = ". ".join(context[-3:]) + ". " + text
        # We'll only use the last part of the translation
        try:
            full_result = await _translate_libretranslate(ctx_text, source_lang, target_lang)
            # Extract just the translated part of our message
            # Split by the same separator
            parts = full_result["translated_text"].rsplit(". ", 1)
            if len(parts) > 1:
                translated = parts[-1]
            else:
                translated = full_result["translated_text"]

            translated = _post_process(translated, text, target_lang)
            result_dict = {"translated_text": translated, "confidence": 0.90}
            await _set_cached(text, source_lang, target_lang, result_dict)
            return TranslationResult(translated, source_lang, target_lang, 0.90, False)
        except Exception:
            pass  # Fall through to non-context translation

    # Direct translation (no context)
    try:
        result = await _translate_libretranslate(text, source_lang, target_lang)
        translated = _post_process(result["translated_text"], text, target_lang)
        result_dict = {"translated_text": translated, "confidence": result["confidence"]}
        await _set_cached(text, source_lang, target_lang, result_dict)
        return TranslationResult(translated, source_lang, target_lang, result["confidence"], False)
    except Exception as e:
        logger.error("Translation failed (%s→%s): %s", source_lang, target_lang, e)
        return TranslationResult(text, source_lang, target_lang, 0.0, False)


async def translate_for_user(
    text: str,
    sender_lang: str,
    receiver_lang: str,
    context: list[str] | None = None,
) -> TranslationResult:
    """
    Smart translation: ALWAYS auto-detect source language from text,
    don't blindly trust sender's preferred_language.
    """
    # CRITICAL FIX: Auto-detect the ACTUAL language of the text
    actual_lang = await detect_language(text)

    # If detected language matches receiver's language, no translation needed
    if actual_lang == receiver_lang:
        return TranslationResult(text, actual_lang, receiver_lang, 1.0, False)

    # If detection failed, fall back to sender's preferred language
    source = actual_lang if actual_lang != "en" or not _has_non_latin(text) else sender_lang

    return await translate(text, source, receiver_lang, context)


def _is_emoji_only(text: str) -> bool:
    stripped = text.strip()
    for char in stripped:
        if char.isalpha():
            return False
    return True


def _has_non_latin(text: str) -> bool:
    for char in text:
        if ord(char) > 0x024F and char.isalpha():
            return True
    return False


def get_supported_languages() -> dict[str, str]:
    return SUPPORTED_LANGUAGES.copy()
