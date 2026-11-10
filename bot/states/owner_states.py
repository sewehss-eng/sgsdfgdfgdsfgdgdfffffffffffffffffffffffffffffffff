"""FSM-состояния меню владельца."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
    root_folder = State()
    page_size = State()
    tpl_page_size = State()


class CategoryStates(StatesGroup):
    # Добавление
    add_title = State()
    add_emoji = State()
    add_kind = State()      # выбор: папка или контейнер подкатегорий
    add_folder = State()
    add_order = State()
    # Редактирование одного поля
    edit_field = State()
    # Ввод значения плейсхолдера (этап/предмет/...)
    var_value = State()


class TemplateStates(StatesGroup):
    # Добавление
    add_title = State()
    add_body = State()       # многострочный ввод, завершается «✅ Готово»
    add_bind = State()
    add_order = State()
    # Редактирование одного поля
    edit_field = State()
    edit_body = State()


class UserStates(StatesGroup):
    add_id = State()
