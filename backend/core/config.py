from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    app_env: str = "development"
    frontend_url: str = "http://localhost:3000"

    jwt_secret: str
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 7

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    # Per user and problem
    submit_cooldown_sec: int = 30
    submit_daily_cap: int = 20
    max_code_bytes: int = 100_000

    # Seeds of the held-out contest instances are derived from this; defaults to JWT_SECRET.
    heldout_secret: str = ""

    # AI features: off unless a key is set. Gemini's free tier is small, so it is kept
    # for image input and as a fallback.
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_daily_limit: int = 18
    ai_daily_limit_per_user: int = 20
    ai_daily_limit_global: int = 500
    llm_price_in_per_million: float = 0.0
    llm_price_out_per_million: float = 0.0

    # Browser integrity signals of tests are deleted after this many days
    integrity_log_retention_days: int = 30

    admin_email: str = ""
    admin_password: str = ""

    @property
    def secure_cookies(self) -> bool:
        return self.app_env != "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
