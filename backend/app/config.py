from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://nexly:nexly_secret@localhost:5432/nexly"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    otp_expiry_seconds: int = 300
    jwt_expiry_minutes: int = 10080  # 7 days
    media_dir: str = "./media"
    sms_provider: str = "console"  # "console" logs OTP, swap for real provider

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
