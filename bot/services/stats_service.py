"""
stats_service — агрегированная статистика для меню владельца.
Тонкая обёртка над repository + форматирование.
"""
from __future__ import annotations

from bot.db import repository as repo


async def summary_text() -> str:
    active = await repo.count_active_users()
    total = await repo.count_users()
    events = await repo.total_link_events()
    d7 = await repo.activity_last_days(7)
    d30 = await repo.activity_last_days(30)
    return (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{total}</b> (активных {active})\n"
        f"🔗 Всего выдач ссылок: <b>{events}</b>\n"
        f"📈 За 7 дней: <b>{d7}</b> · за 30 дней: <b>{d30}</b>"
    )


async def top_folders_text() -> str:
    rows = await repo.top_folders(5)
    if not rows:
        return "Пока нет данных по папкам."
    lines = ["🏆 <b>Топ-5 папок</b>:"]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. {_esc(r['drive_item_name'])} — {r['cnt']}")
    return "\n".join(lines)


async def top_users_text() -> str:
    rows = await repo.top_users(5)
    if not rows:
        return "Пока нет данных по пользователям."
    lines = ["🏆 <b>Топ-5 пользователей</b>:"]
    for i, r in enumerate(rows, 1):
        name = _user_label(r)
        lines.append(f"{i}. {name} — {r['cnt']}")
    return "\n".join(lines)


async def activity_text(days: int) -> str:
    cnt = await repo.activity_last_days(days)
    return f"📈 <b>Активность за {days} дней</b>: {cnt} выдач."


def _user_label(row) -> str:
    uname = row["username"]
    if uname:
        return "@" + _esc(uname)
    full = row["full_name"]
    if full:
        return _esc(full)
    return f"id {row['user_id']}"


def _esc(text: str | None) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
