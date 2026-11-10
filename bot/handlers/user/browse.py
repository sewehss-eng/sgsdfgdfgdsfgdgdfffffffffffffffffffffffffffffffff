"""
Навигация по папкам Google Drive.
render_folder — общая функция отрисовки (используется и при открытии категории).
"""
from __future__ import annotations

import logging

from aiogram import Bot, F
from aiogram.types import CallbackQuery

from bot.config import settings
from bot.db import repository as repo
from bot.handlers.user.router import router_user
from bot.keyboards.callbacks import FolderCb
from bot.keyboards.user_kb import browse_kb
from bot.services import settings_service
from bot.services.drive_service import (
    DriveAccessError,
    DriveError,
    DriveService,
)

log = logging.getLogger(__name__)


async def render_folder(
    call: CallbackQuery,
    bot: Bot,
    category_id: int,
    folder_id: str,
    page: int,
    is_category_root: bool = False,
) -> None:
    """Загружает содержимое папки и редактирует сообщение."""
    drive = DriveService.get()
    category = await repo.get_category(category_id)
    page_size = await settings_service.get_page_size()

    try:
        meta = await drive.get_item(folder_id, with_parents=True)
        items = await drive.list_children(folder_id)
    except DriveAccessError as e:
        log.error("Нет доступа к папке %s: %s", folder_id, e)
        await _notify_owner_no_access(bot, folder_id, str(e))
        await call.answer("Нет доступа к папке. Обратитесь к владельцу.", show_alert=True)
        return
    except DriveError as e:
        log.error("Drive API error (%s): %s", folder_id, e)
        await call.answer("Не удалось получить данные. Попробуйте позже.", show_alert=True)
        return

    folder_name = meta.get("name", "Папка")

    # Родитель для кнопки «Назад».
    # В корне категории назад не предлагаем (там есть «🏠 Категории»).
    parent_folder = None
    if not is_category_root:
        parents = meta.get("parents") or []
        # Если родитель — это корневая папка категории или выше, назад ведёт к ней.
        parent_folder = parents[0] if parents else None
        # Не даём уйти выше корня категории.
        if parent_folder and category and parent_folder == category["folder_id"]:
            pass  # вернёмся в корень категории

    if not items:
        text = f"📂 <b>{_esc(folder_name)}</b>\n\nЗдесь пока ничего нет."
    else:
        text = f"📂 <b>{_esc(folder_name)}</b>\n\nВыберите папку или файл:"

    kb = browse_kb(
        items=items,
        category_id=category_id,
        current_folder=folder_id,
        parent_folder=parent_folder,
        page=page,
        page_size=page_size,
    )
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()


@router_user.callback_query(FolderCb.filter())
async def on_folder(call: CallbackQuery, callback_data: FolderCb, bot: Bot) -> None:
    await render_folder(
        call=call,
        bot=bot,
        category_id=callback_data.cat,
        folder_id=callback_data.fid,
        page=callback_data.page,
        is_category_root=False,
    )


async def _notify_owner_no_access(bot: Bot, folder_id: str, err: str) -> None:
    drive = DriveService.get()
    text = (
        "⚠️ <b>Нет доступа к папке Google Drive</b>\n\n"
        f"folder_id: <code>{folder_id}</code>\n"
        f"Ошибка: <code>{_esc(err)[:300]}</code>\n\n"
        f"Проверьте, что сервисному аккаунту выдан доступ:\n"
        f"<code>{drive.service_account_email}</code>"
    )
    try:
        await bot.send_message(settings.superadmin_id, text)
    except Exception as e:  # noqa: BLE001
        log.error("Не удалось уведомить владельца: %s", e)


def _esc(text: str | None) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
