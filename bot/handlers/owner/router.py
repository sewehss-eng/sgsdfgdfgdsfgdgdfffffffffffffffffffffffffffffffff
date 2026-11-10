"""Общий роутер меню владельца с жёстким фильтром IsOwner."""
from __future__ import annotations

from aiogram import Router

from bot.middlewares.access import IsOwner

router_owner = Router(name="owner")
# Жёсткая проверка: только SUPERADMIN_ID, и для сообщений, и для callback.
router_owner.message.filter(IsOwner())
router_owner.callback_query.filter(IsOwner())
