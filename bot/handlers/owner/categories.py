"""
📁 Категории и подкатегории — полный CRUD через меню владельца (FSM).

Категория может быть:
  • 'folder'    — привязана к папке Google Drive;
  • 'container' — содержит подкатегории (папку не имеет).

Значения плейсхолдеров (этап/предмет/год/регион/класс) задаются для
категории и наследуются подкатегориями (ближняя перекрывает родителя).
"""
from __future__ import annotations

import logging

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.db import repository as repo
from bot.handlers.owner.router import router_owner
from bot.keyboards.callbacks import OwnerCatCb, OwnerCb
from bot.keyboards.owner_kb import (
    categories_list_kb,
    category_card_kb,
    category_kind_kb,
    category_vars_kb,
    cancel_kb,
    skip_cancel_kb,
)
from bot.services import settings_service
from bot.services.drive_service import (
    DriveError,
    DriveService,
    extract_folder_id,
)
from bot.states.owner_states import CategoryStates

log = logging.getLogger(__name__)


# ======================================================================
#  СПИСОК (по уровням)
# ======================================================================
@router_owner.callback_query(OwnerCb.filter(F.action == "categories"))
async def open_root_list(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    root = await settings_service.get_root_folder_id()
    if not root:
        await call.answer("Сначала заполните root folder в Настройках.", show_alert=True)
        return
    await _render_list(call, parent_id=None)


@router_owner.callback_query(OwnerCatCb.filter(F.action == "list"))
async def open_level_list(call: CallbackQuery, callback_data: OwnerCatCb, state: FSMContext) -> None:
    await state.clear()
    pid = int(callback_data.arg or "0")
    await _render_list(call, parent_id=None if pid == 0 else pid)


async def _render_list(call: CallbackQuery, parent_id: int | None) -> None:
    cats = await repo.list_children_categories(parent_id, active_only=False)
    parent = await repo.get_category(parent_id) if parent_id else None
    where = "📁 <b>Категории</b>" if parent is None else f"📂 <b>{_esc(parent['title'])}</b> → подкатегории"
    text = where + "\n\n" + ("Список пуст. Добавьте первую." if not cats else "Выберите элемент:")
    await call.message.edit_text(
        text, reply_markup=categories_list_kb(cats, parent_id=parent_id, parent=parent)
    )
    await call.answer()


# ======================================================================
#  КАРТОЧКА
# ======================================================================
@router_owner.callback_query(OwnerCatCb.filter(F.action == "open"))
async def open_category(call: CallbackQuery, callback_data: OwnerCatCb, state: FSMContext) -> None:
    await state.clear()
    c = await repo.get_category(callback_data.id)
    if not c:
        await call.answer("Категория не найдена.", show_alert=True)
        return
    await _render_card(call, c)


async def _render_card(call: CallbackQuery, c) -> None:
    await call.message.edit_text(
        await _card_text(c),
        reply_markup=category_card_kb(c, is_container=(c["kind"] == "container")),
    )
    await call.answer()


async def _card_text(c) -> str:
    status = "✅ активна" if c["is_active"] else "⛔ выключена"
    emoji = c["emoji"] or "—"
    kind = "📂 контейнер (подкатегории)" if c["kind"] == "container" else "📁 папка Drive"
    lines = [
        f"📁 <b>{_esc(c['title'])}</b>\n",
        f"Тип: {kind}",
        f"Emoji: {emoji}",
    ]
    if c["kind"] != "container":
        lines.append(f"Folder ID: <code>{c['folder_id']}</code>")
        child_count = len(await repo.list_children_categories(c["id"], active_only=False))
    else:
        child_count = len(await repo.list_children_categories(c["id"], active_only=False))
        lines.append(f"Подкатегорий: {child_count}")
    lines.append(f"Порядок: {c['sort_order']}")
    lines.append(f"Статус: {status}")
    # Свои значения плейсхолдеров.
    own = await repo.get_category_vars(c["id"])
    if own:
        vals = ", ".join(f"{k}={v}" for k, v in own.items())
        lines.append(f"🏷 Значения: {_esc(vals)}")
    return "\n".join(lines)


# ======================================================================
#  TOGGLE / DELETE
# ======================================================================
@router_owner.callback_query(OwnerCatCb.filter(F.action == "toggle"))
async def toggle_category(call: CallbackQuery, callback_data: OwnerCatCb) -> None:
    c = await repo.get_category(callback_data.id)
    if not c:
        await call.answer("Категория не найдена.", show_alert=True)
        return
    await repo.update_category(c["id"], is_active=0 if c["is_active"] else 1)
    c = await repo.get_category(callback_data.id)
    await _render_card(call, c)


@router_owner.callback_query(OwnerCatCb.filter(F.action == "del"))
async def delete_category(call: CallbackQuery, callback_data: OwnerCatCb) -> None:
    c = await repo.get_category(callback_data.id)
    parent_id = c["parent_id"] if c else None
    await repo.soft_delete_category(callback_data.id)
    await call.answer("Удалено (вместе с подкатегориями)")
    await _render_list(call, parent_id=parent_id)


# ======================================================================
#  ЗНАЧЕНИЯ ПЛЕЙСХОЛДЕРОВ
# ======================================================================
async def _placeholders_for_category(cid: int) -> list[str]:
    """
    Все кастомные плейсхолдеры, которые встречаются в шаблонах, доступных
    этой категории (её собственные + глобальные), плюс те, для которых уже
    заданы значения. Без фиксированного списка — что в шаблонах, то и показываем.
    """
    from bot.services import template_service

    found: list[str] = []
    templates = await repo.list_templates_for_category(cid)
    for t in templates:
        for ph in template_service.custom_placeholders(t["body"]):
            if ph not in found:
                found.append(ph)
    # Плюс уже заданные значения (вдруг плейсхолдер убрали из шаблона).
    for k in (await repo.get_vars_with_inheritance(cid)).keys():
        if k not in found:
            found.append(k)
    return found


@router_owner.callback_query(OwnerCatCb.filter(F.action == "vars"))
async def open_vars(call: CallbackQuery, callback_data: OwnerCatCb, state: FSMContext) -> None:
    await state.clear()
    cid = callback_data.id
    own = await repo.get_category_vars(cid)
    inherited = await repo.get_vars_with_inheritance(cid)
    placeholders = await _placeholders_for_category(cid)

    lines = ["🏷 <b>Значения плейсхолдеров</b>\n",
             "Бот сам находит <code>{...}</code> в ваших шаблонах.",
             "Задайте значение — оно подставится автоматически.",
             "Подкатегории наследуют значения родителя.\n"]
    if inherited:
        lines.append("Текущие (с учётом наследования):")
        for k, v in inherited.items():
            src = "" if k in own else " <i>(унаследовано)</i>"
            lines.append(f"• <b>{k}</b> = {_esc(v)}{src}")
    if not placeholders:
        lines.append(
            "\n<i>В шаблонах этой категории пока нет плейсхолдеров кроме "
            "{name}/{url}. Добавьте {что-то} в текст шаблона — и он появится здесь.</i>"
        )
    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=category_vars_kb(cid, own, placeholders),
    )
    await call.answer()


@router_owner.callback_query(OwnerCatCb.filter(F.action == "var_set"))
async def var_set_start(call: CallbackQuery, callback_data: OwnerCatCb, state: FSMContext) -> None:
    await state.update_data(cat_id=callback_data.id, var_key=callback_data.arg)
    await state.set_state(CategoryStates.var_value)
    await call.message.edit_text(
        f"🏷 Введите значение для <b>{{{callback_data.arg}}}</b>\n"
        f"(или отправьте «-», чтобы очистить):",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router_owner.message(CategoryStates.var_value)
async def var_set_save(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    cid = data["cat_id"]
    key = data["var_key"]
    raw = (message.text or "").strip()
    if raw == "-":
        await repo.delete_category_var(cid, key)
        msg = f"🏷 Значение «{key}» очищено."
    else:
        await repo.set_category_var(cid, key, raw)
        msg = f"🏷 {key} = {raw}"
    await state.clear()
    own = await repo.get_category_vars(cid)
    placeholders = await _placeholders_for_category(cid)
    await message.answer(
        msg, reply_markup=category_vars_kb(cid, own, placeholders)
    )


# ======================================================================
#  ДОБАВЛЕНИЕ (FSM)
# ======================================================================
@router_owner.callback_query(OwnerCatCb.filter(F.action == "add"))
async def add_start(call: CallbackQuery, callback_data: OwnerCatCb, state: FSMContext) -> None:
    parent_id = int(callback_data.arg or "0")
    await state.update_data(parent_id=None if parent_id == 0 else parent_id)
    await state.set_state(CategoryStates.add_title)
    where = "в корень" if parent_id == 0 else "в подкатегорию"
    await call.message.edit_text(
        f"➕ <b>Новая категория</b> ({where})\n\nВведите название:",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router_owner.message(CategoryStates.add_title)
async def add_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не может быть пустым.")
        return
    await state.update_data(title=title)
    await state.set_state(CategoryStates.add_emoji)
    await message.answer("😀 Введите emoji (или пропустите):", reply_markup=skip_cancel_kb())


@router_owner.message(CategoryStates.add_emoji)
async def add_emoji(message: Message, state: FSMContext) -> None:
    await state.update_data(emoji=(message.text or "").strip())
    await _ask_kind(message, state)


@router_owner.callback_query(OwnerCb.filter(F.action == "skip"), CategoryStates.add_emoji)
async def add_emoji_skip(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(emoji="")
    await _ask_kind(call.message, state)
    await call.answer()


async def _ask_kind(message: Message, state: FSMContext) -> None:
    await state.set_state(CategoryStates.add_kind)
    await message.answer(
        "Что это будет?\n\n"
        "📁 <b>Папка</b> — привязка к папке Google Drive (внутри — файлы).\n"
        "📂 <b>Контейнер</b> — внутри будут подкатегории.",
        reply_markup=category_kind_kb(),
    )


@router_owner.callback_query(OwnerCatCb.filter(F.action == "kind"), CategoryStates.add_kind)
async def add_kind(call: CallbackQuery, callback_data: OwnerCatCb, state: FSMContext) -> None:
    kind = callback_data.arg  # folder | container
    await state.update_data(kind=kind)
    if kind == "container":
        # Контейнеру папка не нужна — сразу порядок.
        await state.set_state(CategoryStates.add_order)
        await call.message.edit_text(
            "🔢 Введите порядок (число) или пропустите:", reply_markup=skip_cancel_kb()
        )
        await call.answer()
        return
    # Папка — спросим folder_id.
    await state.set_state(CategoryStates.add_folder)
    drive = DriveService.get()
    await call.message.edit_text(
        "🗂 Пришлите ссылку на папку Google Drive или folder_id.\n\n"
        f"Email сервисного аккаунта (дайте доступ):\n"
        f"<code>{drive.service_account_email}</code>",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router_owner.message(CategoryStates.add_folder)
async def add_folder(message: Message, state: FSMContext) -> None:
    folder_id = extract_folder_id(message.text or "")
    if not folder_id:
        await message.answer("Не удалось распознать folder_id. Пришлите ссылку или ID.")
        return
    drive = DriveService.get()
    try:
        await drive.validate_folder(folder_id)
    except DriveError as e:
        await message.answer(
            "❌ Папка недоступна или это не папка.\n"
            "Проверьте, что вы дали доступ сервисному аккаунту:\n"
            f"<code>{drive.service_account_email}</code>\n\n<i>{str(e)[:200]}</i>"
        )
        return
    await state.update_data(folder_id=folder_id)
    await state.set_state(CategoryStates.add_order)
    await message.answer("🔢 Введите порядок (число) или пропустите:", reply_markup=skip_cancel_kb())


@router_owner.message(CategoryStates.add_order)
async def add_order(message: Message, state: FSMContext) -> None:
    order = _parse_int(message.text)
    if order is None:
        await message.answer("Нужно целое число. Или нажмите «Пропустить».")
        return
    await _finish_add(message, state, order)


@router_owner.callback_query(OwnerCb.filter(F.action == "skip"), CategoryStates.add_order)
async def add_order_skip(call: CallbackQuery, state: FSMContext) -> None:
    await _finish_add(call.message, state, 0)
    await call.answer()


async def _finish_add(message: Message, state: FSMContext, order: int) -> None:
    data = await state.get_data()
    cid = await repo.create_category(
        title=data["title"],
        emoji=data.get("emoji", ""),
        folder_id=data.get("folder_id", ""),
        sort_order=order,
        parent_id=data.get("parent_id"),
        kind=data.get("kind", "folder"),
    )
    await state.clear()
    c = await repo.get_category(cid)
    kb = category_card_kb(c, is_container=(c["kind"] == "container"))
    await message.answer("✅ Категория добавлена.\n\n" + await _card_text(c), reply_markup=kb)


# ======================================================================
#  РЕДАКТИРОВАНИЕ ПОЛЯ (FSM)
# ======================================================================
@router_owner.callback_query(OwnerCatCb.filter(F.action == "field"))
async def edit_field_start(call: CallbackQuery, callback_data: OwnerCatCb, state: FSMContext) -> None:
    await state.update_data(cat_id=callback_data.id, field=callback_data.field)
    await state.set_state(CategoryStates.edit_field)
    prompts = {
        "title": "Введите новое название:",
        "emoji": "Введите новый emoji:",
        "folder_id": "Пришлите ссылку/ID новой папки:",
        "sort_order": "Введите новый порядок (число):",
    }
    await call.message.edit_text(
        f"✏️ {prompts.get(callback_data.field, 'Новое значение:')}",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router_owner.message(CategoryStates.edit_field)
async def edit_field_save(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    cid = data["cat_id"]
    field = data["field"]
    raw = (message.text or "").strip()

    if field == "folder_id":
        folder_id = extract_folder_id(raw)
        if not folder_id:
            await message.answer("Не удалось распознать folder_id.")
            return
        drive = DriveService.get()
        try:
            await drive.validate_folder(folder_id)
        except DriveError as e:
            await message.answer(f"❌ Папка недоступна.\n<i>{str(e)[:200]}</i>")
            return
        await repo.update_category(cid, folder_id=folder_id)
    elif field == "sort_order":
        order = _parse_int(raw)
        if order is None:
            await message.answer("Нужно целое число.")
            return
        await repo.update_category(cid, sort_order=order)
    elif field == "title":
        if not raw:
            await message.answer("Название не может быть пустым.")
            return
        await repo.update_category(cid, title=raw)
    elif field == "emoji":
        await repo.update_category(cid, emoji=raw)

    await state.clear()
    c = await repo.get_category(cid)
    kb = category_card_kb(c, is_container=(c["kind"] == "container"))
    await message.answer("✅ Сохранено.\n\n" + await _card_text(c), reply_markup=kb)


@router_owner.callback_query(OwnerCatCb.filter(F.action == "tpls"))
async def category_templates(call: CallbackQuery, callback_data: OwnerCatCb, state: FSMContext) -> None:
    """Шаблоны, привязанные к этой категории (+ напоминание про глобальные)."""
    await state.clear()
    cid = callback_data.id
    c = await repo.get_category(cid)
    if not c:
        await call.answer("Категория не найдена.", show_alert=True)
        return
    tpls = await repo.list_templates_by_category(cid)
    lines = [f"✉️ <b>Шаблоны категории «{_esc(c['title'])}»</b>\n"]
    if tpls:
        for t in tpls:
            mark = "✅" if t["is_active"] else "⛔"
            lines.append(f"{mark} {_esc(t['title'])}")
    else:
        lines.append("<i>Своих шаблонов нет. Используются глобальные.</i>")
    lines.append("\nДобавить/изменить шаблоны: раздел «✉️ Шаблоны» главного меню.")
    from bot.keyboards.callbacks import OwnerCb as _OwnerCb
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="✉️ К шаблонам", callback_data=_OwnerCb(action="templates"))
    kb.button(text="⬅️ К категории", callback_data=OwnerCatCb(action="open", id=cid))
    kb.adjust(1)
    await call.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())
    await call.answer()


def _parse_int(text: str | None) -> int | None:
    try:
        return int((text or "").strip())
    except ValueError:
        return None


def _esc(text: str | None) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
