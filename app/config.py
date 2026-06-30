# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+psycopg2://kevin:Kevin123@localhost:5432/helpdesk"
    DATABASE_URL_ASYNC: str = "postgresql+asyncpg://kevin:Kevin123@localhost:5432/helpdesk"

    # JWT
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours

    # App
    APP_NAME: str = "AI Helpdesk Ticket Assistant"
    DEBUG: bool = True

    # SLA hours by priority (hours from creation to breach)
    SLA_HOURS_CRITICAL: int = 4
    SLA_HOURS_HIGH: int = 8
    SLA_HOURS_MEDIUM: int = 24
    SLA_HOURS_LOW: int = 72

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
