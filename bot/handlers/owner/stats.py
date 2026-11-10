"""📊 Статистика."""
from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.handlers.owner.router import router_owner
from bot.keyboards.callbacks import OwnerCb
from bot.keyboards.owner_kb import stats_kb
from bot.services import stats_service


@router_owner.callback_query(OwnerCb.filter(F.action == "stats"))
async def open_stats(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    text = await stats_service.summary_text()
    await call.message.edit_text(text, reply_markup=stats_kb())
    await call.answer()


@router_owner.callback_query(OwnerCb.filter(F.action == "stats_folders"))
async def stats_folders(call: CallbackQuery) -> None:
    text = await stats_service.summary_text() + "\n\n" + await stats_service.top_folders_text()
    await call.message.edit_text(text, reply_markup=stats_kb())
    await call.answer()


@router_owner.callback_query(OwnerCb.filter(F.action == "stats_users"))
async def stats_users(call: CallbackQuery) -> None:
    text = await stats_service.summary_text() + "\n\n" + await stats_service.top_users_text()
    await call.message.edit_text(text, reply_markup=stats_kb())
    await call.answer()


@router_owner.callback_query(OwnerCb.filter(F.action == "stats_7"))
async def stats_7(call: CallbackQuery) -> None:
    text = await stats_service.summary_text() + "\n\n" + await stats_service.activity_text(7)
    await call.message.edit_text(text, reply_markup=stats_kb())
    await call.answer()


@router_owner.callback_query(OwnerCb.filter(F.action == "stats_30"))
async def stats_30(call: CallbackQuery) -> None:
    text = await stats_service.summary_text() + "\n\n" + await stats_service.activity_text(30)
    await call.message.edit_text(text, reply_markup=stats_kb())
    await call.answer()
