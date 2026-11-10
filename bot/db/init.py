"""
Инициализация БД: соединение, применение DDL, сид настроек и шаблонов.
Единая точка получения соединения aiosqlite.
"""
from __future__ import annotations

import logging

import aiosqlite

from bot.config import settings
from bot.db.models import DEFAULT_SETTINGS, DEFAULT_TEMPLATES, SCHEMA_SQL

log = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None


async def init_db() -> aiosqlite.Connection:
    """Создаёт соединение (singleton), применяет схему и сид-данные."""
    global _db
    if _db is not None:
        return _db

    _db = await aiosqlite.connect(settings.db_path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA foreign_keys = ON;")
    await _db.executescript(SCHEMA_SQL)
    await _db.commit()

    await _migrate(_db)
    await _seed_settings(_db)
    await _seed_templates(_db)

    log.info("БД инициализирована: %s", settings.db_path)
    return _db


def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("БД не инициализирована. Сначала вызовите init_db().")
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def _migrate(db: aiosqlite.Connection) -> None:
    """Безопасные ALTER'ы для БД, созданных до появления подкатегорий."""
    cur = await db.execute("PRAGMA table_info(categories)")
    cols = {row["name"] for row in await cur.fetchall()}
    if "parent_id" not in cols:
        await db.execute("ALTER TABLE categories ADD COLUMN parent_id INTEGER")
        log.info("Миграция: добавлена колонка categories.parent_id")
    if "kind" not in cols:
        await db.execute(
            "ALTER TABLE categories ADD COLUMN kind TEXT NOT NULL DEFAULT 'folder'"
        )
        log.info("Миграция: добавлена колонка categories.kind")
    await db.commit()


async def _seed_settings(db: aiosqlite.Connection) -> None:
    for key, value in DEFAULT_SETTINGS.items():
        await db.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
            (key, value),
        )
    await db.commit()


async def _seed_templates(db: aiosqlite.Connection) -> None:
    cur = await db.execute("SELECT COUNT(*) AS c FROM templates")
    row = await cur.fetchone()
    if row["c"] > 0:
        return  # шаблоны уже есть — не трогаем

    for t in DEFAULT_TEMPLATES:
        await db.execute(
            "INSERT INTO templates(title, body, category_id, sort_order, is_active) "
            "VALUES(?, ?, NULL, ?, 1)",
            (t["title"], t["body"], t["sort_order"]),
        )
    await db.commit()
    log.info("Созданы дефолтные глобальные шаблоны (%d шт.)", len(DEFAULT_TEMPLATES))
