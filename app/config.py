# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings,SettingsConfigDict
from functools import lru_cache
# pyrefly: ignore [missing-import]
from pydantic import Field



class Settings(BaseSettings):
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

   # Database
    DATABASE_URL: str = Field(default="")
    DATABASE_URL_ASYNC: str = Field(default="")

    # JWT
    SECRET_KEY: str = Field(default="")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours

    # App
    APP_NAME: str = "AI Helpdesk Ticket Assistant"
    DEBUG: bool = False

    # SLA hours by priority (hours from creation to breach)
    SLA_HOURS_CRITICAL: int = 4
    SLA_HOURS_HIGH: int = 8
    SLA_HOURS_MEDIUM: int = 24
    SLA_HOURS_LOW: int = 72



@lru_cache()
def get_settings() -> Settings:
    return Settings()
