"""
Smart Translation Service — Google Translate powered, context-aware.

Translation chain:
  1. Auto-detect source language from text
  2. Check Redis cache
  3. Google Translate (primary — high quality, free)
  4. LibreTranslate (fallback — self-hosted)
  5. Post-process for emoji preservation + natural flow
  6. Cache result
"""

import hashlib
import json
import logging
import re
from typing import NamedTuple

import httpx
import redis.asyncio as redis
from deep_translator import GoogleTranslator

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
    "zh-CN": "中文 (Chinese)",
    "ja": "日本語 (Japanese)",
    "ko": "��국어 (Korean)",
    "tr": "Türkçe (Turkish)",
    "hi": "हिन्दी (Hindi)",
    "uk": "Українська (Ukrainian)",
    "nl": "Nederlands (Dutch)",
    "pl": "Polski (Polish)",
    "sv": "Svenska (Swedish)",
    "da": "Dansk (Danish)",
    "fi": "Suomi (Finnish)",
}

# Map our codes to Google Translate codes
_GOOGLE_LANG_MAP = {"zh": "zh-CN", "zh-CN": "zh-CN"}

_LANG_CHAR_RANGES = {
    "fa": re.compile(r'[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]'),
    "ar": re.compile(r'[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]'),
    "zh-CN": re.compile(r'[\u4e00-\u9fff]'),
    "ja": re.compile(r'[\u3040-\u309f\u30a0-\u30ff]'),
    "ko": re.compile(r'[\uac00-\ud7af\u1100-\u11ff]'),
    "hi": re.compile(r'[\u0900-\u097F]'),
    "ru": re.compile(r'[\u0400-\u04FF]'),
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
    h = hashlib.md5(text.strip().encode()).hexdigest()
    return f"tr2:{source}:{target}:{h}"


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
        await r.setex(_cache_key(text, source, target), CACHE_TTL, json.dumps(result, ensure_ascii=False))
    except Exception:
        pass


# ── Language Detection ──


def _detect_by_chars(text: str) -> str | None:
    scores: dict[str, int] = {}
    for lang, pattern in _LANG_CHAR_RANGES.items():
        count = len(pattern.findall(text))
        if count > 0:
            scores[lang] = count

    if not scores:
        return None

    best = max(scores, key=scores.get)
    if best in ("fa", "ar"):
        persian_chars = len(re.findall(r'[گپچژکی]', text))
        return "fa" if persian_chars > 0 else "ar"
    return best


async def detect_language(text: str) -> str:
    if not text or len(text.strip()) < 2:
        return "en"

    char_lang = _detect_by_chars(text)
    if char_lang:
        return char_lang

    # M-15 FIX: Removed wasted Google Translate call. Use LibreTranslate detect only.
    # Try LibreTranslate detect
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{settings.libretranslate_url}/detect", json={"q": text[:100]})
            if resp.status_code == 200:
                data = resp.json()
                if data and data[0].get("confidence", 0) > 20:
                    return data[0]["language"]
    except Exception:
        pass

    return "en"


# ── Translation Backends ──


def _google_translate(text: str, source: str, target: str) -> str:
    """Google Translate — high quality, free."""
    src = _GOOGLE_LANG_MAP.get(source, source)
    tgt = _GOOGLE_LANG_MAP.get(target, target)
    translator = GoogleTranslator(source=src, target=tgt)
    return translator.translate(text)


async def _libretranslate(text: str, source: str, target: str) -> str:
    """LibreTranslate fallback."""
    # Map zh-CN back to zh for LibreTranslate
    src = "zh" if source == "zh-CN" else source
    tgt = "zh" if target == "zh-CN" else target
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{settings.libretranslate_url}/translate", json={
            "q": text, "source": src, "target": tgt, "format": "text",
        })
        resp.raise_for_status()
        return resp.json()["translatedText"]


# ── Post-Processing ──


_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001f926-\U0001f937"
    "\U00010000-\U0010ffff"
    "\u2640-\u2642"
    "\u2600-\u2B55"
    "\u200d\u23cf\u23e9\u231a\ufe0f"
    "]+",
    flags=re.UNICODE,
)


def _extract_emojis(text: str) -> list[str]:
    return _EMOJI_PATTERN.findall(text)


def _post_process(translated: str, original: str, target_lang: str) -> str:
    result = translated

    # Preserve emojis
    orig_emojis = _extract_emojis(original)
    trans_emojis = _extract_emojis(result)
    if orig_emojis and not trans_emojis:
        result = result.rstrip() + " " + "".join(orig_emojis)

    # Fix double punctuation
    result = re.sub(r'\?\?+', '?', result)
    result = re.sub(r'!!+', '!', result)
    result = result.replace("  ", " ").strip()

    return result


# ── Main Translation ──


async def translate(
    text: str,
    source_lang: str,
    target_lang: str,
    context: list[str] | None = None,
) -> TranslationResult:
    if source_lang == target_lang:
        return TranslationResult(text, source_lang, target_lang, 1.0, False)

    if not text or len(text.strip()) < 1 or _is_emoji_only(text):
        return TranslationResult(text, source_lang, target_lang, 1.0, False)

    # Check cache
    cached = await _get_cached(text, source_lang, target_lang)
    if cached:
        return TranslationResult(cached["translated_text"], source_lang, target_lang, cached.get("confidence", 0.95), True)

    # Build text with context for better quality
    translate_text = text
    if context and len(context) > 0:
        # Add context as preceding sentences (Google handles this well)
        ctx = ". ".join(c[:80] for c in context[-2:])
        translate_text = f"{ctx}. {text}"

    # Try Google Translate first (best quality)
    try:
        if context:
            full_translated = _google_translate(translate_text, source_lang, target_lang)
            # Extract our message part (after the last ". ")
            parts = full_translated.rsplit(". ", 1)
            translated = parts[-1] if len(parts) > 1 else full_translated
        else:
            translated = _google_translate(text, source_lang, target_lang)

        translated = _post_process(translated, text, target_lang)
        await _set_cached(text, source_lang, target_lang, {"translated_text": translated, "confidence": 0.95})
        return TranslationResult(translated, source_lang, target_lang, 0.95, False)

    except Exception as e:
        logger.warning("Google Translate failed (%s→%s): %s. Falling back to LibreTranslate.", source_lang, target_lang, e)

    # Fallback: LibreTranslate
    try:
        translated = await _libretranslate(text, source_lang, target_lang)
        translated = _post_process(translated, text, target_lang)
        await _set_cached(text, source_lang, target_lang, {"translated_text": translated, "confidence": 0.80})
        return TranslationResult(translated, source_lang, target_lang, 0.80, False)

    except Exception as e:
        logger.error("All translation backends failed (%s��%s): %s", source_lang, target_lang, e)
        return TranslationResult(text, source_lang, target_lang, 0.0, False)


async def translate_for_user(
    text: str,
    sender_lang: str,
    receiver_lang: str,
    context: list[str] | None = None,
) -> TranslationResult:
    # Auto-detect actual language
    actual_lang = await detect_language(text)

    if actual_lang == receiver_lang:
        return TranslationResult(text, actual_lang, receiver_lang, 1.0, False)

    source = actual_lang
    return await translate(text, source, receiver_lang, context)


def _is_emoji_only(text: str) -> bool:
    stripped = text.strip()
    for char in stripped:
        if char.isalpha():
            return False
    return True


def get_supported_languages() -> dict[str, str]:
    return SUPPORTED_LANGUAGES.copy()
