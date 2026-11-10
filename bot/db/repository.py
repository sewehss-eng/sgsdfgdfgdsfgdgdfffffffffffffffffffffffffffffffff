"""
Репозиторий — все операции с БД в одном месте.
Возвращает aiosqlite.Row (dict-like).
"""
from __future__ import annotations

from typing import Any

import aiosqlite

from bot.db.init import get_db


# =========================================================================
#  USERS
# =========================================================================
async def get_user(telegram_id: int) -> aiosqlite.Row | None:
    db = get_db()
    cur = await db.execute(
        "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
    )
    return await cur.fetchone()


async def upsert_user_seen(
    telegram_id: int, username: str | None, full_name: str | None
) -> None:
    """Обновляет username/full_name/last_seen для существующего пользователя."""
    db = get_db()
    await db.execute(
        """
        UPDATE users
           SET username = ?, full_name = ?, last_seen_at = datetime('now')
         WHERE telegram_id = ?
        """,
        (username, full_name, telegram_id),
    )
    await db.commit()


async def create_user(
    telegram_id: int,
    username: str | None,
    full_name: str | None,
    is_active: bool,
) -> None:
    db = get_db()
    await db.execute(
        """
        INSERT INTO users(telegram_id, username, full_name, is_active)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username = excluded.username,
            full_name = excluded.full_name
        """,
        (telegram_id, username, full_name, int(is_active)),
    )
    await db.commit()


async def set_user_active(telegram_id: int, is_active: bool) -> None:
    db = get_db()
    await db.execute(
        "UPDATE users SET is_active = ? WHERE telegram_id = ?",
        (int(is_active), telegram_id),
    )
    await db.commit()


async def delete_user(telegram_id: int) -> None:
    db = get_db()
    await db.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
    await db.commit()


async def list_users(limit: int, offset: int) -> list[aiosqlite.Row]:
    db = get_db()
    cur = await db.execute(
        "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return list(await cur.fetchall())


async def count_users() -> int:
    db = get_db()
    cur = await db.execute("SELECT COUNT(*) AS c FROM users")
    return (await cur.fetchone())["c"]


async def count_active_users() -> int:
    db = get_db()
    cur = await db.execute("SELECT COUNT(*) AS c FROM users WHERE is_active = 1")
    return (await cur.fetchone())["c"]


# =========================================================================
#  CATEGORIES
# =========================================================================
async def list_categories(active_only: bool = True) -> list[aiosqlite.Row]:
    """Все категории (плоско). Для меню владельца."""
    db = get_db()
    sql = "SELECT * FROM categories"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY sort_order ASC, title ASC"
    cur = await db.execute(sql)
    return list(await cur.fetchall())


async def list_children_categories(
    parent_id: int | None, active_only: bool = True
) -> list[aiosqlite.Row]:
    """Категории/подкатегории с заданным родителем (parent_id=None — корень)."""
    db = get_db()
    sql = "SELECT * FROM categories WHERE "
    sql += "parent_id IS NULL" if parent_id is None else "parent_id = ?"
    params: tuple = () if parent_id is None else (parent_id,)
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY sort_order ASC, title ASC"
    cur = await db.execute(sql, params)
    return list(await cur.fetchall())


async def has_children_categories(parent_id: int, active_only: bool = True) -> bool:
    db = get_db()
    sql = "SELECT 1 FROM categories WHERE parent_id = ?"
    if active_only:
        sql += " AND is_active = 1"
    sql += " LIMIT 1"
    cur = await db.execute(sql, (parent_id,))
    return (await cur.fetchone()) is not None


async def get_category(category_id: int) -> aiosqlite.Row | None:
    db = get_db()
    cur = await db.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
    return await cur.fetchone()


async def create_category(
    title: str,
    emoji: str,
    folder_id: str,
    sort_order: int,
    parent_id: int | None = None,
    kind: str = "folder",
) -> int:
    db = get_db()
    cur = await db.execute(
        "INSERT INTO categories(title, emoji, folder_id, sort_order, parent_id, kind) "
        "VALUES(?, ?, ?, ?, ?, ?)",
        (title, emoji, folder_id, sort_order, parent_id, kind),
    )
    await db.commit()
    return cur.lastrowid


async def update_category(category_id: int, **fields: Any) -> None:
    if not fields:
        return
    db = get_db()
    cols = ", ".join(f"{k} = ?" for k in fields)
    await db.execute(
        f"UPDATE categories SET {cols} WHERE id = ?",
        (*fields.values(), category_id),
    )
    await db.commit()


async def soft_delete_category(category_id: int) -> None:
    """Скрывает категорию и всё её поддерево (рекурсивно)."""
    await update_category(category_id, is_active=0)
    for child in await list_children_categories(category_id, active_only=False):
        await soft_delete_category(child["id"])


# --- Кастомные значения категории (плейсхолдеры) ---
async def get_category_vars(category_id: int) -> dict[str, str]:
    db = get_db()
    cur = await db.execute(
        "SELECT key, value FROM category_vars WHERE category_id = ?", (category_id,)
    )
    return {r["key"]: r["value"] for r in await cur.fetchall()}


async def set_category_var(category_id: int, key: str, value: str) -> None:
    db = get_db()
    await db.execute(
        "INSERT INTO category_vars(category_id, key, value) VALUES(?, ?, ?) "
        "ON CONFLICT(category_id, key) DO UPDATE SET value = excluded.value",
        (category_id, key, value),
    )
    await db.commit()


async def delete_category_var(category_id: int, key: str) -> None:
    db = get_db()
    await db.execute(
        "DELETE FROM category_vars WHERE category_id = ? AND key = ?",
        (category_id, key),
    )
    await db.commit()


async def get_vars_with_inheritance(category_id: int) -> dict[str, str]:
    """
    Значения плейсхолдеров с наследованием от родителей.
    Значение ближней (дочерней) категории перекрывает родительское.
    """
    chain: list[int] = []
    cur_id: int | None = category_id
    seen = set()
    while cur_id is not None and cur_id not in seen:
        seen.add(cur_id)
        chain.append(cur_id)
        cat = await get_category(cur_id)
        cur_id = cat["parent_id"] if cat else None

    merged: dict[str, str] = {}
    # От корня к листу: дочерние перекрывают родительские.
    for cid in reversed(chain):
        merged.update(await get_category_vars(cid))
    return merged


# =========================================================================
#  TEMPLATES
# =========================================================================
async def list_templates(active_only: bool = False) -> list[aiosqlite.Row]:
    db = get_db()
    sql = "SELECT * FROM templates"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY sort_order ASC, id ASC"
    cur = await db.execute(sql)
    return list(await cur.fetchall())


async def get_template(template_id: int) -> aiosqlite.Row | None:
    db = get_db()
    cur = await db.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
    return await cur.fetchone()


async def list_templates_for_category(category_id: int) -> list[aiosqlite.Row]:
    """Активные шаблоны: сначала шаблоны категории, затем глобальные."""
    db = get_db()
    cur = await db.execute(
        """
        SELECT * FROM templates
         WHERE is_active = 1 AND (category_id = ? OR category_id IS NULL)
         ORDER BY (category_id IS NULL) ASC, sort_order ASC, id ASC
        """,
        (category_id,),
    )
    return list(await cur.fetchall())


async def list_templates_by_category(category_id: int) -> list[aiosqlite.Row]:
    db = get_db()
    cur = await db.execute(
        "SELECT * FROM templates WHERE category_id = ? ORDER BY sort_order ASC, id ASC",
        (category_id,),
    )
    return list(await cur.fetchall())


async def create_template(
    title: str, body: str, category_id: int | None, sort_order: int
) -> int:
    db = get_db()
    cur = await db.execute(
        "INSERT INTO templates(title, body, category_id, sort_order) "
        "VALUES(?, ?, ?, ?)",
        (title, body, category_id, sort_order),
    )
    await db.commit()
    return cur.lastrowid


async def update_template(template_id: int, **fields: Any) -> None:
    if not fields:
        return
    db = get_db()
    cols = ", ".join(f"{k} = ?" for k in fields)
    await db.execute(
        f"UPDATE templates SET {cols} WHERE id = ?",
        (*fields.values(), template_id),
    )
    await db.commit()


async def soft_delete_template(template_id: int) -> None:
    await update_template(template_id, is_active=0)


# =========================================================================
#  SETTINGS (key-value)
# =========================================================================
async def get_setting(key: str) -> str | None:
    db = get_db()
    cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cur.fetchone()
    return row["value"] if row else None


async def set_setting(key: str, value: str) -> None:
    db = get_db()
    await db.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    await db.commit()


# =========================================================================
#  LINK EVENTS (аудит)
# =========================================================================
async def log_link_event(
    user_id: int,
    category_id: int | None,
    drive_item_id: str,
    drive_item_name: str,
    item_type: str,
    mode: str,
) -> None:
    db = get_db()
    await db.execute(
        """
        INSERT INTO link_events
            (user_id, category_id, drive_item_id, drive_item_name, item_type, mode)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (user_id, category_id, drive_item_id, drive_item_name, item_type, mode),
    )
    await db.commit()


async def total_link_events() -> int:
    db = get_db()
    cur = await db.execute("SELECT COUNT(*) AS c FROM link_events")
    return (await cur.fetchone())["c"]


async def top_folders(limit: int = 5) -> list[aiosqlite.Row]:
    db = get_db()
    cur = await db.execute(
        """
        SELECT drive_item_name, drive_item_id, COUNT(*) AS cnt
          FROM link_events
         GROUP BY drive_item_id
         ORDER BY cnt DESC
         LIMIT ?
        """,
        (limit,),
    )
    return list(await cur.fetchall())


async def top_users(limit: int = 5) -> list[aiosqlite.Row]:
    db = get_db()
    cur = await db.execute(
        """
        SELECT le.user_id, u.username, u.full_name, COUNT(*) AS cnt
          FROM link_events le
          LEFT JOIN users u ON u.telegram_id = le.user_id
         GROUP BY le.user_id
         ORDER BY cnt DESC
         LIMIT ?
        """,
        (limit,),
    )
    return list(await cur.fetchall())


async def activity_last_days(days: int) -> int:
    db = get_db()
    cur = await db.execute(
        "SELECT COUNT(*) AS c FROM link_events "
        "WHERE created_at >= datetime('now', ?)",
        (f"-{days} days",),
    )
    return (await cur.fetchone())["c"]


async def user_events(user_id: int, limit: int) -> list[aiosqlite.Row]:
    db = get_db()
    cur = await db.execute(
        "SELECT * FROM link_events WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    return list(await cur.fetchall())


async def user_events_count(user_id: int) -> int:
    db = get_db()
    cur = await db.execute(
        "SELECT COUNT(*) AS c FROM link_events WHERE user_id = ?", (user_id,)
    )
    return (await cur.fetchone())["c"]


async def item_events(drive_item_id: str, limit: int) -> list[aiosqlite.Row]:
    db = get_db()
    cur = await db.execute(
        """
        SELECT le.*, u.username, u.full_name
          FROM link_events le
          LEFT JOIN users u ON u.telegram_id = le.user_id
         WHERE le.drive_item_id = ?
         ORDER BY le.created_at DESC
         LIMIT ?
        """,
        (drive_item_id, limit),
    )
    return list(await cur.fetchall())


async def recent_events(limit: int = 50) -> list[aiosqlite.Row]:
    db = get_db()
    cur = await db.execute(
        """
        SELECT le.*, u.username, u.full_name
          FROM link_events le
          LEFT JOIN users u ON u.telegram_id = le.user_id
         ORDER BY le.created_at DESC
         LIMIT ?
        """,
        (limit,),
    )
    return list(await cur.fetchall())


async def recent_events_by_user(user_id: int, limit: int) -> list[aiosqlite.Row]:
    return await user_events(user_id, limit)


async def recent_events_by_category(category_id: int, limit: int) -> list[aiosqlite.Row]:
    db = get_db()
    cur = await db.execute(
        """
        SELECT le.*, u.username, u.full_name
          FROM link_events le
          LEFT JOIN users u ON u.telegram_id = le.user_id
         WHERE le.category_id = ?
         ORDER BY le.created_at DESC
         LIMIT ?
        """,
        (category_id, limit),
    )
    return list(await cur.fetchall())
