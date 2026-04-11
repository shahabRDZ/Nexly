import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://nexly:nexly_secret@localhost:5432/nexly"
    redis_url: str = "redis://localhost:6379/0"
    # C-2 FIX: Generate random secret if not set via env
    secret_key: str = secrets.token_urlsafe(32)
    otp_expiry_seconds: int = 300
    jwt_expiry_minutes: int = 10080
    media_dir: str = "./media"
    sms_provider: str = "console"
    libretranslate_url: str = "http://libretranslate:5000"
    translation_enabled: bool = True
    # CORS
    allowed_origins: str = "*"  # Comma-separated in production: "https://nexly.app,https://app.nexly.com"
    # Admin
    admin_phones: str = ""  # Comma-separated: "+14155551234,+989121234567"
    # File upload
    max_upload_size: int = 50 * 1024 * 1024  # 50MB
    max_avatar_size: int = 5 * 1024 * 1024  # 5MB

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
