"""
👥 Пользователи — список, карточка, блокировка/разблокировка/удаление,
ручное добавление, обработка заявок на доступ.
"""
from __future__ import annotations

import logging

from aiogram import Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.db import repository as repo
from bot.handlers.owner.router import router_owner
from bot.keyboards.callbacks import OwnerCb, UserCb
from bot.keyboards.owner_kb import (
    back_to_menu_kb,
    cancel_kb,
    user_card_kb,
    users_list_kb,
)
from bot.services import settings_service
from bot.states.owner_states import UserStates

log = logging.getLogger(__name__)

PAGE = 10


# ---------- Список ----------
@router_owner.callback_query(OwnerCb.filter(F.action == "users"))
async def list_users(call: CallbackQuery, callback_data: OwnerCb, state: FSMContext) -> None:
    await state.clear()
    page = callback_data.page
    users = await repo.list_users(limit=PAGE + 1, offset=page * PAGE)
    has_next = len(users) > PAGE
    users = users[:PAGE]
    total = await repo.count_users()
    text = f"👥 <b>Пользователи</b> (всего {total})"
    await call.message.edit_text(text, reply_markup=users_list_kb(users, page, has_next))
    await call.answer()


# ---------- Карточка ----------
@router_owner.callback_query(UserCb.filter(F.action == "open"))
async def open_user(call: CallbackQuery, callback_data: UserCb, state: FSMContext) -> None:
    await state.clear()
    await _render_user_card(call, callback_data.uid)


async def _render_user_card(call: CallbackQuery, uid: int) -> None:
    u = await repo.get_user(uid)
    if not u:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    cnt = await repo.user_events_count(uid)
    events = await repo.user_events(uid, 20)
    status = "✅ активен" if u["is_active"] else "⛔ заблокирован"
    uname = ("@" + u["username"]) if u["username"] else "—"

    lines = [
        f"👤 <b>{_esc(u['full_name']) or 'Без имени'}</b>",
        f"Username: {uname}",
        f"ID: <code>{u['telegram_id']}</code>",
        f"Добавлен: {u['created_at']}",
        f"Last seen: {u['last_seen_at'] or '—'}",
        f"Статус: {status}",
        f"Выдач ссылок: {cnt}",
    ]
    if events:
        lines.append("\n<b>Последние события:</b>")
        for e in events:
            lines.append(f"• {e['created_at']} — {_esc(e['drive_item_name'])} ({e['mode']})")
    await call.message.edit_text("\n".join(lines), reply_markup=user_card_kb(u))
    await call.answer()


# ---------- Block / Unblock / Delete ----------
@router_owner.callback_query(UserCb.filter(F.action == "block"))
async def block_user(call: CallbackQuery, callback_data: UserCb, bot: Bot) -> None:
    await repo.set_user_active(callback_data.uid, False)
    await _render_user_card(call, callback_data.uid)
    await _try_notify(bot, callback_data.uid, "⛔ Ваш доступ к боту приостановлен.")


@router_owner.callback_query(UserCb.filter(F.action == "unblock"))
async def unblock_user(call: CallbackQuery, callback_data: UserCb, bot: Bot) -> None:
    await repo.set_user_active(callback_data.uid, True)
    await _render_user_card(call, callback_data.uid)
    await _try_notify(bot, callback_data.uid, "✅ Доступ восстановлен. Откройте /start.")


@router_owner.callback_query(UserCb.filter(F.action == "delete"))
async def delete_user(call: CallbackQuery, callback_data: UserCb) -> None:
    await repo.delete_user(callback_data.uid)
    users = await repo.list_users(limit=PAGE, offset=0)
    await call.message.edit_text(
        "🗑 Пользователь удалён.\n\n👥 <b>Пользователи</b>",
        reply_markup=users_list_kb(users, 0, len(users) >= PAGE),
    )
    await call.answer("Удалено")


# ---------- Заявки на доступ (кнопки под уведомлением) ----------
@router_owner.callback_query(UserCb.filter(F.action == "allow"))
async def allow_request(call: CallbackQuery, callback_data: UserCb, bot: Bot) -> None:
    uid = callback_data.uid
    u = await repo.get_user(uid)
    if u is None:
        await repo.create_user(uid, None, None, is_active=True)
    else:
        await repo.set_user_active(uid, True)
    await call.message.edit_text(f"✅ Доступ выдан пользователю <code>{uid}</code>.")
    await _try_notify(bot, uid, "✅ Вам выдан доступ! Откройте /start.")
    await call.answer()


@router_owner.callback_query(UserCb.filter(F.action == "deny"))
async def deny_request(call: CallbackQuery, callback_data: UserCb, bot: Bot) -> None:
    uid = callback_data.uid
    await call.message.edit_text(f"❌ Заявка пользователя <code>{uid}</code> отклонена.")
    await _try_notify(bot, uid, "❌ В доступе отказано.")
    await call.answer()


# ---------- Ручное добавление ----------
@router_owner.callback_query(OwnerCb.filter(F.action == "user_add"))
async def user_add_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(UserStates.add_id)
    await call.message.edit_text(
        "➕ Введите Telegram ID пользователя (число):", reply_markup=cancel_kb()
    )
    await call.answer()


@router_owner.message(UserStates.add_id)
async def user_add_save(message: Message, state: FSMContext) -> None:
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Нужен числовой Telegram ID.")
        return
    existing = await repo.get_user(uid)
    if existing:
        await repo.set_user_active(uid, True)
        msg = f"ℹ️ Пользователь <code>{uid}</code> уже существовал — активирован."
    else:
        await repo.create_user(uid, None, None, is_active=True)
        msg = f"✅ Пользователь <code>{uid}</code> добавлен и активирован."
    await state.clear()
    await message.answer(msg, reply_markup=back_to_menu_kb())


async def _try_notify(bot: Bot, uid: int, text: str) -> None:
    try:
        await bot.send_message(uid, text)
    except Exception as e:  # noqa: BLE001
        log.info("Не удалось уведомить пользователя %s: %s", uid, e)


def _esc(text: str | None) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
