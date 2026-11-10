"""
Конфигурация бота. ТОЛЬКО секреты из .env (pydantic-settings).
Всё остальное (root folder, page_size, шаблоны, категории и т.п.) — в БД.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(..., alias="BOT_TOKEN")
    superadmin_id: int = Field(..., alias="SUPERADMIN_ID")
    google_service_account_file: str = Field(..., alias="GOOGLE_SERVICE_ACCOUNT_FILE")
    db_path: str = Field("./bot.db", alias="DB_PATH")


settings = Settings()  # читается один раз при импорте
