"""
🔑 Настройки: root folder, page_size, tpl_page_size, logging toggle.
"""
from __future__ import annotations

import logging

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.owner.router import router_owner
from bot.keyboards.callbacks import OwnerCb
from bot.keyboards.owner_kb import back_to_menu_kb, cancel_kb, settings_kb
from bot.services import settings_service
from bot.services.drive_service import (
    DriveError,
    DriveService,
    extract_folder_id,
)
from bot.states.owner_states import SettingsStates

log = logging.getLogger(__name__)


async def _render_settings(call: CallbackQuery) -> None:
    drive = DriveService.get()
    root = await settings_service.get_root_folder_id()
    page_size = await settings_service.get_page_size()
    tpl_ps = await settings_service.get_template_page_size()
    logging_on = await settings_service.is_logging_enabled()

    root_disp = f"<code>{root}</code>" if root else "<i>не задан</i>"
    text = (
        "🔑 <b>Настройки</b>\n\n"
        f"🗂 Root folder: {root_disp}\n"
        f"✉️ Email сервисного аккаунта (дайте ему доступ к папке):\n"
        f"<code>{drive.service_account_email}</code>"
    )
    await call.message.edit_text(
        text, reply_markup=settings_kb(page_size, logging_on, tpl_ps)
    )
    await call.answer()


@router_owner.callback_query(OwnerCb.filter(F.action == "settings"))
async def open_settings(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _render_settings(call)


# --- Root folder ---
@router_owner.callback_query(OwnerCb.filter(F.action == "set_root"))
async def ask_root(call: CallbackQuery, state: FSMContext) -> None:
    drive = DriveService.get()
    await state.set_state(SettingsStates.root_folder)
    await call.message.edit_text(
        "🗂 Пришлите ссылку на корневую папку Google Drive или folder_id.\n\n"
        f"Email сервисного аккаунта (дайте ему доступ):\n"
        f"<code>{drive.service_account_email}</code>",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router_owner.message(SettingsStates.root_folder)
async def save_root(message: Message, state: FSMContext) -> None:
    folder_id = extract_folder_id(message.text or "")
    if not folder_id:
        await message.answer("Не удалось распознать folder_id. Пришлите ссылку или ID ещё раз.")
        return

    drive = DriveService.get()
    try:
        await drive.validate_folder(folder_id)
    except DriveError as e:
        await message.answer(
            "❌ Папка недоступна или это не папка.\n"
            "Проверьте, что вы дали доступ сервисному аккаунту:\n"
            f"<code>{drive.service_account_email}</code>\n\n"
            f"<i>{str(e)[:200]}</i>"
        )
        return

    await settings_service.set_root_folder_id(folder_id)
    await state.clear()
    await message.answer(
        f"✅ Root folder сохранён: <code>{folder_id}</code>",
        reply_markup=back_to_menu_kb(),
    )


# --- Page size ---
@router_owner.callback_query(OwnerCb.filter(F.action == "set_page_size"))
async def ask_page_size(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.page_size)
    await call.message.edit_text(
        "📄 Сколько элементов показывать на странице? Пришлите число (1–50).",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router_owner.message(SettingsStates.page_size)
async def save_page_size(message: Message, state: FSMContext) -> None:
    val = _parse_int(message.text, 1, 50)
    if val is None:
        await message.answer("Нужно число от 1 до 50.")
        return
    await settings_service.set_page_size(val)
    await state.clear()
    await message.answer(f"✅ Элементов на страницу: {val}", reply_markup=back_to_menu_kb())


# --- Template page size ---
@router_owner.callback_query(OwnerCb.filter(F.action == "set_tpl_page"))
async def ask_tpl_page(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.tpl_page_size)
    await call.message.edit_text(
        "✉️ Сколько шаблонов показывать на экране «С готовым текстом»? Число (1–50).",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router_owner.message(SettingsStates.tpl_page_size)
async def save_tpl_page(message: Message, state: FSMContext) -> None:
    val = _parse_int(message.text, 1, 50)
    if val is None:
        await message.answer("Нужно число от 1 до 50.")
        return
    await settings_service.set_template_page_size(val)
    await state.clear()
    await message.answer(f"✅ Шаблонов на экран: {val}", reply_markup=back_to_menu_kb())


# --- Logging toggle ---
@router_owner.callback_query(OwnerCb.filter(F.action == "toggle_logging"))
async def toggle_logging(call: CallbackQuery, state: FSMContext) -> None:
    current = await settings_service.is_logging_enabled()
    await settings_service.set_logging_enabled(not current)
    await _render_settings(call)


def _parse_int(text: str | None, lo: int, hi: int) -> int | None:
    try:
        v = int((text or "").strip())
    except ValueError:
        return None
    return v if lo <= v <= hi else None
