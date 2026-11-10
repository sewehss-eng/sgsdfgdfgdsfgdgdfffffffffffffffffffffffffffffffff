"""
✉️ Шаблоны — полный CRUD через меню владельца (FSM).
Многострочный ввод текста завершается кнопкой «✅ Готово».
"""
from __future__ import annotations

import logging

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.db import repository as repo
from bot.handlers.owner.router import router_owner
from bot.keyboards.callbacks import OwnerCb, OwnerTplCb
from bot.keyboards.owner_kb import (
    back_to_menu_kb,
    body_done_kb,
    cancel_kb,
    skip_cancel_kb,
    template_bind_kb,
    template_card_kb,
    templates_list_kb,
)
from bot.services import template_service
from bot.states.owner_states import TemplateStates

log = logging.getLogger(__name__)

BODY_HINT = (
    "Используйте <code>{name}</code> для названия папки и <code>{url}</code> для ссылки.\n"
    "Переносы строк сохраняются. Отправляйте текст сообщениями, "
    "в конце нажмите «✅ Готово».\n\n"
    "Пример:\n<code>{name}\n🔗 Материал: {url}</code>"
)


# ---------- Список ----------
@router_owner.callback_query(OwnerCb.filter(F.action == "templates"))
async def list_templates(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    tpls = await repo.list_templates(active_only=False)
    text = "✉️ <b>Шаблоны</b>\n\n" + (
        "Список пуст." if not tpls else "🌐 — глобальный, 📁 — привязан к категории."
    )
    await call.message.edit_text(text, reply_markup=templates_list_kb(tpls))
    await call.answer()


# ---------- Карточка ----------
@router_owner.callback_query(OwnerTplCb.filter(F.action == "open"))
async def open_template(call: CallbackQuery, callback_data: OwnerTplCb, state: FSMContext) -> None:
    await state.clear()
    t = await repo.get_template(callback_data.id)
    if not t:
        await call.answer("Шаблон не найден.", show_alert=True)
        return
    await call.message.edit_text(await _card_text(t), reply_markup=template_card_kb(t))
    await call.answer()


async def _card_text(t) -> str:
    status = "✅ активен" if t["is_active"] else "⛔ выключен"
    if t["category_id"] is None:
        bind = "🌐 Глобальный"
    else:
        c = await repo.get_category(t["category_id"])
        bind = f"📁 {c['title']}" if c else f"📁 #{t['category_id']}"
    return (
        f"✉️ <b>{_esc(t['title'])}</b>\n\n"
        f"Привязка: {bind}\n"
        f"Порядок: {t['sort_order']}\n"
        f"Статус: {status}\n\n"
        f"Текст:\n<code>{_esc(t['body'])}</code>"
    )


# ---------- Preview / Toggle / Delete ----------
@router_owner.callback_query(OwnerTplCb.filter(F.action == "preview"))
async def preview_template(call: CallbackQuery, callback_data: OwnerTplCb) -> None:
    t = await repo.get_template(callback_data.id)
    if not t:
        await call.answer("Шаблон не найден.", show_alert=True)
        return
    rendered = template_service.preview(t["body"])
    await call.message.answer(f"👁 <b>Предпросмотр:</b>\n\n{_esc(rendered)}")
    await call.answer()


@router_owner.callback_query(OwnerTplCb.filter(F.action == "toggle"))
async def toggle_template(call: CallbackQuery, callback_data: OwnerTplCb) -> None:
    t = await repo.get_template(callback_data.id)
    if not t:
        await call.answer("Шаблон не найден.", show_alert=True)
        return
    await repo.update_template(t["id"], is_active=0 if t["is_active"] else 1)
    t = await repo.get_template(callback_data.id)
    await call.message.edit_text(await _card_text(t), reply_markup=template_card_kb(t))
    await call.answer("Готово ✅")


@router_owner.callback_query(OwnerTplCb.filter(F.action == "del"))
async def delete_template(call: CallbackQuery, callback_data: OwnerTplCb) -> None:
    await repo.soft_delete_template(callback_data.id)
    tpls = await repo.list_templates(active_only=False)
    await call.message.edit_text(
        "🗑 Шаблон удалён (скрыт).\n\n✉️ <b>Шаблоны</b>",
        reply_markup=templates_list_kb(tpls),
    )
    await call.answer("Удалено")


# ---------- Добавление (FSM) ----------
@router_owner.callback_query(OwnerTplCb.filter(F.action == "add"))
async def add_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TemplateStates.add_title)
    await call.message.edit_text(
        "➕ <b>Новый шаблон</b>\n\nВведите название кнопки (например: «С пометкой \"Материал\"»):",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router_owner.message(TemplateStates.add_title)
async def add_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не может быть пустым.")
        return
    await state.update_data(title=title, body_parts=[])
    await state.set_state(TemplateStates.add_body)
    await message.answer("📝 " + BODY_HINT, reply_markup=body_done_kb())


@router_owner.message(TemplateStates.add_body)
async def add_body_collect(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    parts: list[str] = data.get("body_parts", [])
    parts.append(message.text or "")
    await state.update_data(body_parts=parts)
    await message.answer(
        "Добавлено. Присылайте ещё или нажмите «✅ Готово».",
        reply_markup=body_done_kb(),
    )


@router_owner.callback_query(OwnerTplCb.filter(F.action == "body_done"), TemplateStates.add_body)
async def add_body_done(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    body = "\n".join(data.get("body_parts", [])).strip()
    if not template_service.validate_body(body):
        await call.answer("Шаблон должен содержать {name} и {url}", show_alert=True)
        return
    await state.update_data(body=body)
    cats = await repo.list_categories(active_only=False)
    await state.set_state(TemplateStates.add_bind)
    await call.message.edit_text(
        "🔗 Выберите привязку шаблона:", reply_markup=template_bind_kb(cats)
    )
    await call.answer()


@router_owner.callback_query(OwnerTplCb.filter(F.action == "bind"), TemplateStates.add_bind)
async def add_bind(call: CallbackQuery, callback_data: OwnerTplCb, state: FSMContext) -> None:
    cat_id = int(callback_data.arg or "0")
    await state.update_data(category_id=None if cat_id == 0 else cat_id)
    await state.set_state(TemplateStates.add_order)
    await call.message.edit_text(
        "🔢 Введите порядок (число) или пропустите:", reply_markup=skip_cancel_kb()
    )
    await call.answer()


@router_owner.message(TemplateStates.add_order)
async def add_order(message: Message, state: FSMContext) -> None:
    order = _parse_int(message.text)
    if order is None:
        await message.answer("Нужно целое число или «Пропустить».")
        return
    await _finish_add(message, state, order)


@router_owner.callback_query(OwnerCb.filter(F.action == "skip"), TemplateStates.add_order)
async def add_order_skip(call: CallbackQuery, state: FSMContext) -> None:
    await _finish_add(call.message, state, 0)
    await call.answer()


async def _finish_add(message: Message, state: FSMContext, order: int) -> None:
    data = await state.get_data()
    tid = await repo.create_template(
        title=data["title"],
        body=data["body"],
        category_id=data.get("category_id"),
        sort_order=order,
    )
    await state.clear()
    t = await repo.get_template(tid)
    await message.answer("✅ Шаблон добавлен.\n\n" + await _card_text(t), reply_markup=template_card_kb(t))


# ---------- Редактирование поля ----------
@router_owner.callback_query(OwnerTplCb.filter(F.action == "field"))
async def edit_field_start(call: CallbackQuery, callback_data: OwnerTplCb, state: FSMContext) -> None:
    field = callback_data.field
    await state.update_data(tpl_id=callback_data.id, field=field)

    if field == "body":
        await state.update_data(body_parts=[])
        await state.set_state(TemplateStates.edit_body)
        await call.message.edit_text("📝 " + BODY_HINT, reply_markup=body_done_kb())
        await call.answer()
        return

    if field == "bind":
        cats = await repo.list_categories(active_only=False)
        await state.set_state(TemplateStates.edit_field)
        await call.message.edit_text(
            "🔗 Выберите новую привязку:", reply_markup=template_bind_kb(cats)
        )
        await call.answer()
        return

    prompts = {"title": "Введите новое название:", "sort_order": "Введите порядок (число):"}
    await state.set_state(TemplateStates.edit_field)
    await call.message.edit_text(f"✏️ {prompts.get(field, 'Новое значение:')}", reply_markup=cancel_kb())
    await call.answer()


@router_owner.callback_query(OwnerTplCb.filter(F.action == "bind"), TemplateStates.edit_field)
async def edit_bind(call: CallbackQuery, callback_data: OwnerTplCb, state: FSMContext) -> None:
    data = await state.get_data()
    tid = data["tpl_id"]
    cat_id = int(callback_data.arg or "0")
    await repo.update_template(tid, category_id=None if cat_id == 0 else cat_id)
    await state.clear()
    t = await repo.get_template(tid)
    await call.message.edit_text("✅ Сохранено.\n\n" + await _card_text(t), reply_markup=template_card_kb(t))
    await call.answer()


@router_owner.message(TemplateStates.edit_field)
async def edit_field_save(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    tid = data["tpl_id"]
    field = data["field"]
    raw = (message.text or "").strip()

    if field == "title":
        if not raw:
            await message.answer("Название не может быть пустым.")
            return
        await repo.update_template(tid, title=raw)
    elif field == "sort_order":
        order = _parse_int(raw)
        if order is None:
            await message.answer("Нужно целое число.")
            return
        await repo.update_template(tid, sort_order=order)

    await state.clear()
    t = await repo.get_template(tid)
    await message.answer("✅ Сохранено.\n\n" + await _card_text(t), reply_markup=template_card_kb(t))


# ---------- Редактирование body (многострочно) ----------
@router_owner.message(TemplateStates.edit_body)
async def edit_body_collect(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    parts: list[str] = data.get("body_parts", [])
    parts.append(message.text or "")
    await state.update_data(body_parts=parts)
    await message.answer("Добавлено. Ещё или «✅ Готово».", reply_markup=body_done_kb())


@router_owner.callback_query(OwnerTplCb.filter(F.action == "body_done"), TemplateStates.edit_body)
async def edit_body_done(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    tid = data["tpl_id"]
    body = "\n".join(data.get("body_parts", [])).strip()
    if not template_service.validate_body(body):
        await call.answer("Шаблон должен содержать {name} и {url}", show_alert=True)
        return
    await repo.update_template(tid, body=body)
    await state.clear()
    t = await repo.get_template(tid)
    await call.message.edit_text("✅ Текст обновлён.\n\n" + await _card_text(t), reply_markup=template_card_kb(t))
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
