"""
Общие хендлеры: /start, выдача категорий, заявки на доступ,
кнопка «Меню владельца» для суперадмина, обработка устаревших callback.
"""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings
from bot.db import repository as repo
from bot.keyboards.callbacks import CategoryCb, NavCb
from bot.keyboards.owner_kb import access_request_kb
from bot.keyboards.user_kb import categories_kb

log = logging.getLogger(__name__)
router_common = Router(name="common")


@router_common.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    user = message.from_user
    is_owner = user.id == settings.superadmin_id
    db_user = await repo.get_user(user.id)

    # Незнакомец (и не владелец) — заявка на доступ
    if not is_owner and (db_user is None or not db_user["is_active"]):
        if db_user is None:
            await repo.create_user(user.id, user.username, user.full_name, is_active=False)
        await _notify_owner_access_request(bot, user)
        await message.answer(
            "👋 Привет! Доступ к материалам пока не выдан.\n"
            "Я отправил владельцу заявку — ожидайте решения."
        )
        return

    await _show_categories(message, is_owner)


async def _show_categories(message: Message, is_owner: bool) -> None:
    categories = await repo.list_children_categories(None, active_only=True)
    if not categories:
        text = (
            "📂 Пока нет доступных категорий.\n"
            "Загляните позже — владелец ещё наполняет витрину."
        )
        if is_owner:
            text += "\n\nНажмите «🛠 Меню владельца», чтобы добавить категории."
        await message.answer(text, reply_markup=_start_kb([], is_owner))
        return
    await message.answer(
        "📚 <b>Выберите категорию:</b>",
        reply_markup=_start_kb(categories, is_owner),
    )


def _start_kb(categories, is_owner: bool):
    """Корневые категории + кнопка «Меню владельца» для суперадмина."""
    kb = InlineKeyboardBuilder()
    for c in categories:
        emoji = (c["emoji"] + " ") if c["emoji"] else "📁 "
        kb.button(text=f"{emoji}{c['title']}", callback_data=CategoryCb(id=c["id"]))
    kb.adjust(1)
    if is_owner:
        kb.row(
            InlineKeyboardButton(text="🛠 Меню владельца", callback_data="open_admin")
        )
    return kb.as_markup()


@router_common.callback_query(NavCb.filter(F.action == "home"))
async def nav_home(call: CallbackQuery) -> None:
    is_owner = call.from_user.id == settings.superadmin_id
    categories = await repo.list_children_categories(None, active_only=True)
    if not categories:
        await call.message.edit_text(
            "📂 Пока нет доступных категорий.", reply_markup=_start_kb([], is_owner)
        )
        await call.answer()
        return
    await call.message.edit_text(
        "📚 <b>Выберите категорию:</b>",
        reply_markup=_start_kb(categories, is_owner),
    )
    await call.answer()


@router_common.callback_query(NavCb.filter(F.action == "noop"))
async def nav_noop(call: CallbackQuery) -> None:
    await call.answer()


async def _notify_owner_access_request(bot: Bot, user) -> None:
    uname = ("@" + user.username) if user.username else "(без username)"
    text = (
        "🔔 <b>Заявка на доступ</b>\n\n"
        f"Пользователь {uname}\n"
        f"Имя: {user.full_name}\n"
        f"ID: <code>{user.id}</code>\n\n"
        "Разрешить доступ?"
    )
    try:
        await bot.send_message(
            settings.superadmin_id, text, reply_markup=access_request_kb(user.id)
        )
    except Exception as e:  # noqa: BLE001
        log.error("Не удалось отправить заявку владельцу: %s", e)


# Последний в цепочке — устаревшие / неизвестные callback.
@router_common.callback_query()
async def unknown_callback(call: CallbackQuery) -> None:
    await call.answer("Кнопка устарела, откройте /start", show_alert=True)
