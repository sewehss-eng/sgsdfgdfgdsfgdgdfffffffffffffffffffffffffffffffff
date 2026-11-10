"""
AccessMiddleware — единственная точка контроля прав.

Правила:
  • SUPERADMIN_ID — проходит везде (user-часть + меню владельца).
  • Остальные — только user-часть и только при is_active = True.
  • Незнакомец при /start — не пускается, но владелец получает заявку (см. common.py).
  • Прочие сообщения от незнакомца/заблокированного — «Доступ не выдан».

Middleware вешается на user-роутеры. Owner-роутер дополнительно
фильтруется жёстким IsOwner-фильтром.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from bot.config import settings
from bot.db import repository as repo

log = logging.getLogger(__name__)

# Эти команды незнакомцу разрешены (обрабатываются в common.py — заявка на доступ)
_ALLOWED_FOR_STRANGERS = {"/start"}


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        # Владелец — всегда пропускаем, но обновим last_seen/профиль
        if user.id == settings.superadmin_id:
            await _touch_or_create(user, is_active=True)
            data["is_owner"] = True
            return await handler(event, data)

        data["is_owner"] = False
        db_user = await repo.get_user(user.id)

        if db_user and db_user["is_active"]:
            await repo.upsert_user_seen(user.id, user.username, user.full_name)
            return await handler(event, data)

        # --- незнакомец / заблокированный ---
        # /start пропускаем в common.py (там логика заявки)
        if isinstance(event, Message) and (event.text or "").strip() in _ALLOWED_FOR_STRANGERS:
            return await handler(event, data)

        # Остальное — блок
        if isinstance(event, Message):
            await event.answer("⛔ Доступ не выдан. Обратитесь к владельцу.")
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔ Доступ не выдан. Обратитесь к владельцу.", show_alert=True)
        return None


async def _touch_or_create(user: User, is_active: bool) -> None:
    existing = await repo.get_user(user.id)
    if existing is None:
        await repo.create_user(user.id, user.username, user.full_name, is_active)
    await repo.upsert_user_seen(user.id, user.username, user.full_name)


class IsOwner(BaseFilter):
    """Фильтр для owner-роутера: доступ строго по SUPERADMIN_ID."""

    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id == settings.superadmin_id)
