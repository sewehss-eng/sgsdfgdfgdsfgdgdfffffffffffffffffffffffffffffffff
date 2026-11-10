"""
/admin — вход в меню владельца, главное меню, онбординг, отмена FSM.
"""
from __future__ import annotations

import logging

from aiogram import F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.owner.router import router_owner
from bot.keyboards.callbacks import OwnerCb
from bot.keyboards.owner_kb import (
    back_to_menu_kb,
    main_menu_kb,
    onboarding_kb,
)
from bot.services import settings_service
from bot.services.drive_service import DriveService

log = logging.getLogger(__name__)

MENU_TEXT = "🛠 <b>Меню владельца</b>\n\nВыберите раздел:"


async def _show_menu(target: Message | CallbackQuery) -> None:
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(MENU_TEXT, reply_markup=main_menu_kb())
        await target.answer()
    else:
        await target.answer(MENU_TEXT, reply_markup=main_menu_kb())


@router_owner.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    root = await settings_service.get_root_folder_id()
    if not root:
        await _show_onboarding(message)
        return
    await _show_menu(message)


@router_owner.callback_query(F.data == "open_admin")
async def open_admin_from_start(call: CallbackQuery, state: FSMContext) -> None:
    """Кнопка «🛠 Меню владельца» из /start."""
    await state.clear()
    root = await settings_service.get_root_folder_id()
    if not root:
        await _show_onboarding(call.message)
        await call.answer()
        return
    await _show_menu(call)


async def _show_onboarding(message: Message) -> None:
    drive = DriveService.get()
    text = (
        "👋 <b>Первичная настройка</b>\n\n"
        "1️⃣ Дайте доступ (Viewer) сервисному аккаунту к корневой папке Google Drive:\n"
        f"<code>{drive.service_account_email}</code>\n\n"
        "2️⃣ Вставьте ссылку на корневую папку (кнопка ниже).\n\n"
        "3️⃣ Готово — после этого добавьте категории.\n\n"
        "ℹ️ ID корневой папки задаётся здесь, а не в .env."
    )
    await message.answer(text, reply_markup=onboarding_kb())


@router_owner.callback_query(OwnerCb.filter(F.action == "menu"))
async def back_to_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _show_menu(call)


@router_owner.callback_query(OwnerCb.filter(F.action == "cancel"))
async def cancel_fsm(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        "❌ Отменено.", reply_markup=back_to_menu_kb()
    )
    await call.answer()
