import logging
import secrets

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Generate once per process — stable across the lifetime
_DEFAULT_SECRET = secrets.token_urlsafe(32)


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://nexly:nexly_secret@localhost:5432/nexly"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = ""
    otp_expiry_seconds: int = 300
    jwt_expiry_minutes: int = 10080
    media_dir: str = "./media"
    sms_provider: str = "console"
    libretranslate_url: str = "http://libretranslate:5000"
    translation_enabled: bool = True
    allowed_origins: str = "*"
    admin_phones: str = ""
    max_upload_size: int = 50 * 1024 * 1024
    max_avatar_size: int = 5 * 1024 * 1024

    @model_validator(mode="after")
    def ensure_secret_key(self):
        """H-1 FIX: Never use empty secret key."""
        if not self.secret_key or len(self.secret_key) < 16:
            self.secret_key = _DEFAULT_SECRET
            logger.warning("SECRET_KEY not set or too short — using auto-generated key. Set SECRET_KEY env var for production!")
        return self

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
