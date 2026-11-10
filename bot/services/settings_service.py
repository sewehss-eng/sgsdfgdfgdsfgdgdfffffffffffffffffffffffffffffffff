"""
settings_service — типизированный доступ к key-value настройкам из БД.
"""
from __future__ import annotations

from bot.db import repository as repo


async def get_root_folder_id() -> str:
    return (await repo.get_setting("google_root_folder_id")) or ""


async def set_root_folder_id(folder_id: str) -> None:
    await repo.set_setting("google_root_folder_id", folder_id)


async def get_page_size() -> int:
    return _to_int(await repo.get_setting("page_size"), 10)


async def set_page_size(value: int) -> None:
    await repo.set_setting("page_size", str(value))


async def get_template_page_size() -> int:
    return _to_int(await repo.get_setting("template_page_size"), 10)


async def set_template_page_size(value: int) -> None:
    await repo.set_setting("template_page_size", str(value))


async def is_logging_enabled() -> bool:
    return (await repo.get_setting("logging_enabled")) == "1"


async def set_logging_enabled(enabled: bool) -> None:
    await repo.set_setting("logging_enabled", "1" if enabled else "0")


async def get_history_limit() -> int:
    return _to_int(await repo.get_setting("history_limit"), 50)


async def set_history_limit(value: int) -> None:
    await repo.set_setting("history_limit", str(value))


def _to_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
