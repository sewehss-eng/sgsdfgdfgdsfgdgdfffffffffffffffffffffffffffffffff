"""
Выдача ссылок в трёх режимах: кнопкой / текстом / с готовым текстом.
Каждая выдача логируется (если включено в настройках).
"""
from __future__ import annotations

import logging

from aiogram import Bot, F
from aiogram.types import CallbackQuery

from bot.config import settings
from bot.db import repository as repo
from bot.handlers.user.browse import _notify_owner_no_access
from bot.handlers.user.router import router_user
from bot.keyboards.callbacks import ItemCb, LinkModeCb, TemplateCb
from bot.keyboards.user_kb import (
    link_modes_kb,
    open_link_button_kb,
    templates_choose_kb,
)
from bot.services import settings_service, template_service, region_service
from bot.services.drive_service import (
    DriveAccessError,
    DriveError,
    DriveService,
    is_folder,
)

log = logging.getLogger(__name__)


def _item_type_flag(t: str) -> bool:
    """t: 'f' -> folder(True), 'd' -> file(False)."""
    return t == "f"


def _pick_material_template(templates):
    """
    Шаблон для «✉️ С готовым текстом»: предпочитаем «С пометкой "Материал"»
    (по слову «материал» в названии). Если такого нет — первый доступный.
    """
    for t in templates:
        if "материал" in (t["title"] or "").lower():
            return t
    return templates[0]


async def _render_material(drive, cat: int, iid: str, body: str, name: str, url: str) -> str:
    extra = await repo.get_vars_with_inheritance(cat)
    category = await repo.get_category(cat)
    root = category["folder_id"] if category else None
    region = await region_service.resolve_region(drive, iid, category_root=root)
    if region:
        extra = region_service.region_values(extra, region)
    rendered = template_service.render(body, name=name, url=url, extra=extra)
    if region:
        rendered = region_service.correct_region_label(rendered, region)
    return rendered


# --- Шаг 1: пользователь выбрал элемент → меню из 3 режимов ---
@router_user.callback_query(ItemCb.filter())
async def item_menu(call: CallbackQuery, callback_data: ItemCb, bot: Bot) -> None:
    drive = DriveService.get()
    try:
        meta = await drive.get_item(callback_data.iid)
    except DriveAccessError as e:
        await _notify_owner_no_access(bot, callback_data.iid, str(e))
        await call.answer("Нет доступа к элементу. Обратитесь к владельцу.", show_alert=True)
        return
    except DriveError:
        await call.answer("Не удалось получить данные. Попробуйте позже.", show_alert=True)
        return

    name = meta.get("name", "Элемент")
    folder = is_folder(meta.get("mimeType", ""))
    await call.message.edit_text(
        f"🔗 <b>{_esc(name)}</b>",
        reply_markup=link_modes_kb(
            callback_data.cat, callback_data.iid, "f" if folder else "d"
        ),
    )
    await call.answer()


# --- Шаг 2: выбран режим ---
@router_user.callback_query(LinkModeCb.filter())
async def link_mode(call: CallbackQuery, callback_data: LinkModeCb, bot: Bot) -> None:
    cat = callback_data.cat
    iid = callback_data.iid
    folder = _item_type_flag(callback_data.t)
    mode = callback_data.m

    drive = DriveService.get()
    try:
        meta = await drive.get_item(iid)
        await drive.ensure_public(iid)
    except DriveAccessError as e:
        await _notify_owner_no_access(bot, iid, str(e))
        await call.answer("Нет доступа к элементу. Обратитесь к владельцу.", show_alert=True)
        return
    except DriveError:
        await call.answer("Не удалось получить данные. Попробуйте позже.", show_alert=True)
        return

    name = meta.get("name", "Элемент")
    url = DriveService.public_url(iid, folder)
    item_type = "folder" if folder else "file"

    if mode == "button":
        await call.message.answer(
            f"Ссылка на «{_esc(name)}»:",
            reply_markup=open_link_button_kb(name, url),
        )
        await _log(call.from_user.id, cat, iid, name, item_type, "button")
        await call.answer()

    elif mode == "raw":
        await call.message.answer(f"<code>{_esc(url)}</code>")
        await _log(call.from_user.id, cat, iid, name, item_type, "raw")
        await call.answer()

    elif mode == "tpl":
        # Сразу выдаём готовым текстом по шаблону «С пометкой "Материал"».
        templates = await repo.list_templates_for_category(cat)
        if not templates:
            await call.answer("Для этой категории нет шаблонов.", show_alert=True)
            return
        tpl = _pick_material_template(templates)
        try:
            rendered = await _render_material(drive, cat, iid, tpl["body"], name, url)
        except DriveError:
            log.exception("Не удалось определить регион материала %s", iid)
            await call.answer("Не удалось проверить регион. Попробуйте позже.", show_alert=True)
            return
        # Два сообщения: с <code> (копируется тапом) и без (переслать как есть).
        await call.message.answer(f"<code>{_esc(rendered)}</code>")
        await call.message.answer(rendered)
        await _log(call.from_user.id, cat, iid, name, item_type, f"template:{tpl['id']}")
        await call.answer("Готово ✅")


# --- Шаг 3 (для tpl): выбран конкретный шаблон ---
@router_user.callback_query(TemplateCb.filter())
async def apply_template(call: CallbackQuery, callback_data: TemplateCb, bot: Bot) -> None:
    cat = callback_data.cat
    iid = callback_data.iid
    folder = _item_type_flag(callback_data.t)

    tpl = await repo.get_template(callback_data.tid)
    if not tpl or not tpl["is_active"]:
        await call.answer("Шаблон недоступен.", show_alert=True)
        return

    drive = DriveService.get()
    try:
        meta = await drive.get_item(iid)
        await drive.ensure_public(iid)
    except DriveAccessError as e:
        await _notify_owner_no_access(bot, iid, str(e))
        await call.answer("Нет доступа к элементу. Обратитесь к владельцу.", show_alert=True)
        return
    except DriveError:
        await call.answer("Не удалось получить данные. Попробуйте позже.", show_alert=True)
        return

    name = meta.get("name", "Элемент")
    url = DriveService.public_url(iid, folder)
    try:
        rendered = await _render_material(drive, cat, iid, tpl["body"], name, url)
    except DriveError:
        log.exception("Не удалось определить регион материала %s", iid)
        await call.answer("Не удалось проверить регион. Попробуйте позже.", show_alert=True)
        return

    # Два сообщения: с <code> (копируется одним тапом) и без (переслать как есть).
    await call.message.answer(f"<code>{_esc(rendered)}</code>")
    await call.message.answer(rendered)

    await _log(
        call.from_user.id, cat, iid, name,
        "folder" if folder else "file", f"template:{tpl['id']}"
    )
    await call.answer("Готово ✅")


async def _log(
    user_id: int,
    category_id: int,
    item_id: str,
    item_name: str,
    item_type: str,
    mode: str,
) -> None:
    if not await settings_service.is_logging_enabled():
        return
    try:
        await repo.log_link_event(
            user_id=user_id,
            category_id=category_id,
            drive_item_id=item_id,
            drive_item_name=item_name,
            item_type=item_type,
            mode=mode,
        )
    except Exception as e:  # noqa: BLE001
        log.error("Не удалось залогировать выдачу ссылки: %s", e)


def _esc(text: str | None) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
