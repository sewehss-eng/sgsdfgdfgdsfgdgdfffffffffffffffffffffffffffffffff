"""Открытие категории → подкатегории или содержимое папки Drive."""
from __future__ import annotations

import logging

from aiogram import Bot, F
from aiogram.types import CallbackQuery

from bot.config import settings
from bot.db import repository as repo
from bot.handlers.user.browse import render_folder
from bot.handlers.user.router import router_user
from bot.keyboards.callbacks import CategoryCb
from bot.keyboards.user_kb import categories_kb

log = logging.getLogger(__name__)


@router_user.callback_query(CategoryCb.filter())
async def open_category(call: CallbackQuery, callback_data: CategoryCb, bot: Bot) -> None:
    category = await repo.get_category(callback_data.id)
    if not category or not category["is_active"]:
        await call.answer("Категория недоступна. Откройте /start", show_alert=True)
        return

    # Контейнер или есть вложенные активные подкатегории → показываем их.
    children = await repo.list_children_categories(category["id"], active_only=True)
    if category["kind"] == "container" or children:
        if not children:
            await call.answer("Здесь пока нет подкатегорий.", show_alert=True)
            return
        emoji = (category["emoji"] + " ") if category["emoji"] else "📂 "
        await call.message.edit_text(
            f"{emoji}<b>{_esc(category['title'])}</b>\n\nВыберите подкатегорию:",
            reply_markup=categories_kb(children, parent_id=category["parent_id"]),
        )
        await call.answer()
        return

    # Иначе это категория-папка → открываем Drive.
    await render_folder(
        call=call,
        bot=bot,
        category_id=category["id"],
        folder_id=category["folder_id"],
        page=0,
        is_category_root=True,
    )


def _esc(text: str | None) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

