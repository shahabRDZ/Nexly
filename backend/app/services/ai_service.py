"""
AI Service — Smart Reply, Chat Summary, Voice-to-Text, AI Bot.

Uses a pluggable backend approach:
- Default: Rule-based fallback (no external API needed)
- Optional: pluggable external or local LLM via config

For voice-to-text, uses the LibreTranslate/Whisper approach or fallback.
"""
import logging
import re

logger = logging.getLogger(__name__)


async def generate_smart_replies(history: list[dict], language: str = "en") -> list[str]:
    """
    Generate 3 smart reply suggestions based on conversation history.
    history: [{"role": "me"|"them", "text": "..."}, ...]
    """
    if not history:
        return _default_greetings(language)

    last_msg = history[-1]["text"].lower().strip() if history[-1]["text"] else ""

    # Rule-based smart replies
    if _is_question(last_msg):
        return _reply_to_question(last_msg, language)
    elif _is_greeting(last_msg):
        return _greeting_replies(language)
    elif _is_thanks(last_msg):
        return _thanks_replies(language)
    elif _is_farewell(last_msg):
        return _farewell_replies(language)
    elif _is_positive(last_msg):
        return _positive_replies(language)
    elif _is_negative(last_msg):
        return _sympathy_replies(language)
    else:
        return _generic_replies(language)


async def summarize_chat(texts: list[str], language: str = "en") -> str:
    """Summarize a list of message texts."""
    if not texts:
        return "No messages to summarize."

    total = len(texts)
    # Simple extractive summary: pick key messages
    if total <= 5:
        summary_texts = texts
    else:
        # Pick first, middle, and last messages plus any questions
        indices = {0, total // 4, total // 2, 3 * total // 4, total - 1}
        for i, t in enumerate(texts):
            if "?" in t:
                indices.add(i)
        summary_texts = [texts[i] for i in sorted(indices) if i < total]

    bullet_points = "\n".join(f"• {t[:100]}" for t in summary_texts[:10])

    summaries = {
        "en": f"Summary of {total} messages:\n{bullet_points}",
        "fa": f"خلاصه {total} پیام:\n{bullet_points}",
        "ar": f"ملخص {total} رسالة:\n{bullet_points}",
        "es": f"Resumen de {total} mensajes:\n{bullet_points}",
        "fr": f"Résumé de {total} messages:\n{bullet_points}",
        "de": f"Zusammenfassung von {total} Nachrichten:\n{bullet_points}",
    }
    return summaries.get(language, summaries["en"])


async def transcribe_voice_url(media_url: str, language: str = "en") -> str:
    """
    Transcribe voice message audio to text.
    In production, integrate Whisper API or similar.
    """
    # Placeholder — in production, download the file and send to Whisper
    return f"[Voice message — transcription requires Whisper API integration. File: {media_url}]"


async def ask_ai_bot(message: str, language: str = "en", user_name: str = "") -> str:
    """AI chatbot response. Uses rule-based fallback."""
    msg = message.lower().strip()

    if _is_greeting(msg):
        greetings = {
            "en": f"Hey {user_name}! I'm Nexly AI. How can I help you today?",
            "fa": f"سلام {user_name}! من هوش مصنوعی Nexly هستم. چطور می‌تونم کمکت کنم؟",
            "es": f"¡Hola {user_name}! Soy Nexly AI. ¿Cómo puedo ayudarte?",
        }
        return greetings.get(language, greetings["en"])

    if any(w in msg for w in ["help", "کمک", "ayuda", "aide"]):
        helps = {
            "en": "I can help you with:\n• Smart replies\n• Chat summaries\n• Translation\n• General questions\n\nJust ask!",
            "fa": "من می‌تونم کمکت کنم در:\n• پاسخ‌های هوشمند\n• خلاصه چت\n• ترجمه\n• سوالات عمومی\n\nفقط بپرس!",
        }
        return helps.get(language, helps["en"])

    if any(w in msg for w in ["weather", "هوا", "tiempo", "météo"]):
        return {
            "en": "I can't check weather yet, but that feature is coming soon! 🌤️",
            "fa": "هنوز نمی‌تونم هوا رو چک کنم، ولی این قابلیت به زودی اضافه میشه! 🌤️",
        }.get(language, "Weather feature coming soon! 🌤️")

    # Default response
    defaults = {
        "en": f"That's interesting! I'm still learning, but I'm here to help. Try asking me to summarize a chat or suggest replies.",
        "fa": f"جالبه! من هنوز در حال یادگیری هستم، ولی اینجام تا کمک کنم. از من بخواه چت‌ها رو خلاصه کنم یا پاسخ پیشنهاد بدم.",
        "es": f"¡Interesante! Todavía estoy aprendiendo, pero estoy aquí para ayudar.",
    }
    return defaults.get(language, defaults["en"])


# ── Helper functions ──

def _is_question(text: str) -> bool:
    return "?" in text or text.startswith(("what", "how", "why", "when", "where", "who", "do", "is", "can", "چطور", "آیا", "کجا", "چرا"))

def _is_greeting(text: str) -> bool:
    greetings = {"hi", "hello", "hey", "سلام", "های", "hola", "bonjour", "ciao", "merhaba", "hallo"}
    return any(g in text.split() for g in greetings)

def _is_thanks(text: str) -> bool:
    return any(w in text for w in ["thank", "ممنون", "مرسی", "gracias", "merci", "danke"])

def _is_farewell(text: str) -> bool:
    return any(w in text for w in ["bye", "خداحافظ", "بای", "adiós", "au revoir", "tschüss"])

def _is_positive(text: str) -> bool:
    return any(w in text for w in ["great", "awesome", "good", "nice", "عالی", "خوب", "عالیه"])

def _is_negative(text: str) -> bool:
    return any(w in text for w in ["sad", "bad", "sorry", "ناراحت", "بد", "متأسف"])


def _default_greetings(lang: str) -> list[str]:
    return {"fa": ["سلام!", "سلام، خوبی؟", "👋"], "es": ["¡Hola!", "¿Qué tal?", "👋"]}.get(lang, ["Hi!", "How are you?", "👋"])

def _greeting_replies(lang: str) -> list[str]:
    return {"fa": ["سلام! خوبی؟", "به به! چه خبر؟", "سلام! 😊"], "es": ["¡Hola! ¿Cómo estás?", "¡Hey! 👋", "¿Qué tal?"]}.get(lang, ["Hey! How are you?", "Hi there! 👋", "Hello!"])

def _reply_to_question(text: str, lang: str) -> list[str]:
    return {"fa": ["بله", "نه", "بذار فکر کنم"], "es": ["Sí", "No", "Déjame pensar"]}.get(lang, ["Yes", "No", "Let me think about it"])

def _thanks_replies(lang: str) -> list[str]:
    return {"fa": ["خواهش می‌کنم!", "قابلی نداشت 😊", "❤️"], "es": ["¡De nada!", "No hay problema 😊", "❤️"]}.get(lang, ["You're welcome!", "No problem 😊", "❤️"])

def _farewell_replies(lang: str) -> list[str]:
    return {"fa": ["خداحافظ! 👋", "شب بخیر", "فعلاً بای!"], "es": ["¡Adiós! 👋", "Hasta luego", "¡Nos vemos!"]}.get(lang, ["Bye! 👋", "See you later!", "Take care!"])

def _positive_replies(lang: str) -> list[str]:
    return {"fa": ["عالیه! 🎉", "خوشحالم!", "آفرین!"], "es": ["¡Genial! 🎉", "¡Me alegro!", "¡Bien!"]}.get(lang, ["That's great! 🎉", "Awesome!", "Love it!"])

def _sympathy_replies(lang: str) -> list[str]:
    return {"fa": ["متأسفم 😢", "امیدوارم بهتر بشه", "❤️"], "es": ["Lo siento 😢", "Espero que mejore", "❤️"]}.get(lang, ["I'm sorry to hear that 😢", "Hope it gets better", "❤️"])

def _generic_replies(lang: str) -> list[str]:
    return {"fa": ["آره", "خب", "جالبه!"], "es": ["Sí", "OK", "¡Interesante!"]}.get(lang, ["OK", "Got it", "Interesting!"])
