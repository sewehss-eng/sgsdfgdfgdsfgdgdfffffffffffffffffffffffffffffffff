"""📜 Журнал действий — последние 50 событий link_events."""
from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.db import repository as repo
from bot.handlers.owner.router import router_owner
from bot.keyboards.callbacks import OwnerCb
from bot.keyboards.owner_kb import back_to_menu_kb


@router_owner.callback_query(OwnerCb.filter(F.action == "audit"))
async def open_audit(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    events = await repo.recent_events(50)
    if not events:
        await call.message.edit_text(
            "📜 <b>Журнал действий</b>\n\nПока пусто.", reply_markup=back_to_menu_kb()
        )
        await call.answer()
        return

    lines = ["📜 <b>Журнал действий</b> (последние 50):\n"]
    for e in events:
        who = ("@" + e["username"]) if e["username"] else (e["full_name"] or f"id {e['user_id']}")
        lines.append(
            f"• {e['created_at']} — {_esc(who)} → "
            f"{_esc(e['drive_item_name'])} ({e['item_type']}/{e['mode']})"
        )
    text = "\n".join(lines)
    # Телеграм ограничивает 4096 символов
    if len(text) > 4000:
        text = text[:3990] + "\n…"
    await call.message.edit_text(text, reply_markup=back_to_menu_kb())
    await call.answer()


def _esc(text: str | None) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
