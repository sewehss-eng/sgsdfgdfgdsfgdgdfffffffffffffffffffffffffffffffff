"""Клавиатуры меню владельца."""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.callbacks import (
    OwnerCatCb,
    OwnerCb,
    OwnerTplCb,
    UserCb,
)

CANCEL_TEXT = "❌ Отмена"


def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔑 Настройки", callback_data=OwnerCb(action="settings"))
    kb.button(text="📁 Категории", callback_data=OwnerCb(action="categories"))
    kb.button(text="✉️ Шаблоны", callback_data=OwnerCb(action="templates"))
    kb.button(text="👥 Пользователи", callback_data=OwnerCb(action="users"))
    kb.button(text="📊 Статистика", callback_data=OwnerCb(action="stats"))
    kb.button(text="📜 Журнал действий", callback_data=OwnerCb(action="audit"))
    kb.adjust(1)
    return kb.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В меню", callback_data=OwnerCb(action="menu"))
    return kb.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=CANCEL_TEXT, callback_data=OwnerCb(action="cancel"))
    return kb.as_markup()


# ---------- Settings ----------
def settings_kb(page_size: int, logging_on: bool, tpl_page_size: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗂 Root folder", callback_data=OwnerCb(action="set_root"))
    kb.button(text=f"📄 Элементов на страницу: {page_size}",
              callback_data=OwnerCb(action="set_page_size"))
    kb.button(text=f"✉️ Шаблонов на экран: {tpl_page_size}",
              callback_data=OwnerCb(action="set_tpl_page"))
    kb.button(
        text=f"📝 Логирование выдач: {'ВКЛ ✅' if logging_on else 'ВЫКЛ ⛔'}",
        callback_data=OwnerCb(action="toggle_logging"),
    )
    kb.button(text="⬅️ В меню", callback_data=OwnerCb(action="menu"))
    kb.adjust(1)
    return kb.as_markup()


# ---------- Categories ----------
def categories_list_kb(categories, parent_id: int | None = None, parent=None) -> InlineKeyboardMarkup:
    """
    Список категорий текущего уровня.
    parent_id — чей это уровень (None = корень); parent — объект родителя (для «Назад»).
    """
    kb = InlineKeyboardBuilder()
    for c in categories:
        mark = "✅" if c["is_active"] else "⛔"
        emoji = c["emoji"] or ("📂" if c["kind"] == "container" else "📁")
        kind_tag = "📂" if c["kind"] == "container" else ""
        kb.button(
            text=f"{mark} {emoji} {c['title']} {kind_tag}(#{c['sort_order']})",
            callback_data=OwnerCatCb(action="open", id=c["id"]),
        )
    kb.adjust(1)
    # Добавление на текущий уровень.
    add = InlineKeyboardBuilder()
    add.button(
        text="➕ Добавить сюда",
        callback_data=OwnerCatCb(action="add", arg=str(parent_id or 0)),
    )
    add.adjust(1)
    kb.attach(add)
    # Навигация.
    nav = InlineKeyboardBuilder()
    if parent is not None:
        back_to = parent["parent_id"] or 0
        nav.button(
            text="⬆️ На уровень выше",
            callback_data=OwnerCatCb(action="list", arg=str(back_to)),
        )
    nav.button(text="⬅️ В меню", callback_data=OwnerCb(action="menu"))
    nav.adjust(1)
    kb.attach(nav)
    return kb.as_markup()


def category_card_kb(category, is_container: bool) -> InlineKeyboardMarkup:
    cid = category["id"]
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Название", callback_data=OwnerCatCb(action="field", id=cid, field="title"))
    kb.button(text="😀 Emoji", callback_data=OwnerCatCb(action="field", id=cid, field="emoji"))
    if is_container:
        kb.button(text="📂 Открыть подкатегории", callback_data=OwnerCatCb(action="list", arg=str(cid)))
    else:
        kb.button(text="🗂 Folder ID", callback_data=OwnerCatCb(action="field", id=cid, field="folder_id"))
    kb.button(text="🔢 Порядок", callback_data=OwnerCatCb(action="field", id=cid, field="sort_order"))
    kb.button(text="🏷 Значения плейсхолдеров", callback_data=OwnerCatCb(action="vars", id=cid))
    toggle = "⛔ Выключить" if category["is_active"] else "✅ Включить"
    kb.button(text=toggle, callback_data=OwnerCatCb(action="toggle", id=cid))
    kb.button(text="✉️ Шаблоны категории", callback_data=OwnerCatCb(action="tpls", id=cid))
    kb.button(text="🗑 Удалить", callback_data=OwnerCatCb(action="del", id=cid))
    parent_level = category["parent_id"] or 0
    kb.button(text="⬅️ К списку", callback_data=OwnerCatCb(action="list", arg=str(parent_level)))
    kb.adjust(2, 1, 1, 1, 1, 1, 1, 1)
    return kb.as_markup()


def category_kind_kb() -> InlineKeyboardMarkup:
    """Выбор типа создаваемой категории."""
    kb = InlineKeyboardBuilder()
    kb.button(text="📁 Папка Google Drive", callback_data=OwnerCatCb(action="kind", arg="folder"))
    kb.button(text="📂 Контейнер (подкатегории)", callback_data=OwnerCatCb(action="kind", arg="container"))
    kb.button(text=CANCEL_TEXT, callback_data=OwnerCb(action="cancel"))
    kb.adjust(1)
    return kb.as_markup()


def category_vars_kb(cid: int, vars_set: dict, placeholders: list[str]) -> InlineKeyboardMarkup:
    """Кнопки для каждого плейсхолдера: задать/изменить значение."""
    kb = InlineKeyboardBuilder()
    for ph in placeholders:
        val = vars_set.get(ph, "")
        label = f"{ph}: {val}" if val else f"{ph}: — задать"
        kb.button(text=label, callback_data=OwnerCatCb(action="var_set", id=cid, arg=ph))
    kb.button(text="⬅️ К категории", callback_data=OwnerCatCb(action="open", id=cid))
    kb.adjust(1)
    return kb.as_markup()


# ---------- Templates ----------
def templates_list_kb(templates) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in templates:
        mark = "✅" if t["is_active"] else "⛔"
        bind = "🌐" if t["category_id"] is None else "📁"
        kb.button(
            text=f"{mark} {bind} {t['title']}",
            callback_data=OwnerTplCb(action="open", id=t["id"]),
        )
    kb.button(text="➕ Добавить шаблон", callback_data=OwnerTplCb(action="add"))
    kb.button(text="⬅️ В меню", callback_data=OwnerCb(action="menu"))
    kb.adjust(1)
    return kb.as_markup()


def template_card_kb(template) -> InlineKeyboardMarkup:
    tid = template["id"]
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Название", callback_data=OwnerTplCb(action="field", id=tid, field="title"))
    kb.button(text="📝 Текст", callback_data=OwnerTplCb(action="field", id=tid, field="body"))
    kb.button(text="🔗 Привязка", callback_data=OwnerTplCb(action="field", id=tid, field="bind"))
    kb.button(text="🔢 Порядок", callback_data=OwnerTplCb(action="field", id=tid, field="sort_order"))
    kb.button(text="👁 Предпросмотр", callback_data=OwnerTplCb(action="preview", id=tid))
    toggle = "⛔ Выключить" if template["is_active"] else "✅ Включить"
    kb.button(text=toggle, callback_data=OwnerTplCb(action="toggle", id=tid))
    kb.button(text="🗑 Удалить", callback_data=OwnerTplCb(action="del", id=tid))
    kb.button(text="⬅️ К шаблонам", callback_data=OwnerCb(action="templates"))
    kb.adjust(2, 2, 2, 1, 1)
    return kb.as_markup()


def template_bind_kb(categories) -> InlineKeyboardMarkup:
    """Выбор привязки шаблона: глобальный или конкретная категория."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🌐 Глобальный", callback_data=OwnerTplCb(action="bind", arg="0"))
    for c in categories:
        kb.button(
            text=f"📁 {c['title']}",
            callback_data=OwnerTplCb(action="bind", arg=str(c["id"])),
        )
    kb.button(text=CANCEL_TEXT, callback_data=OwnerCb(action="cancel"))
    kb.adjust(1)
    return kb.as_markup()


def body_done_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Готово", callback_data=OwnerTplCb(action="body_done"))
    kb.button(text=CANCEL_TEXT, callback_data=OwnerCb(action="cancel"))
    kb.adjust(1)
    return kb.as_markup()


def skip_cancel_kb() -> InlineKeyboardMarkup:
    """Для необязательного шага (emoji, порядок)."""
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Пропустить", callback_data=OwnerCb(action="skip"))
    kb.button(text=CANCEL_TEXT, callback_data=OwnerCb(action="cancel"))
    kb.adjust(2)
    return kb.as_markup()


# ---------- Users ----------
def users_list_kb(users, page: int, has_next: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for u in users:
        mark = "✅" if u["is_active"] else "⛔"
        label = ("@" + u["username"]) if u["username"] else (u["full_name"] or str(u["telegram_id"]))
        kb.button(text=f"{mark} {label}", callback_data=UserCb(action="open", uid=u["telegram_id"]))
    kb.adjust(1)

    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="◀️", callback_data=OwnerCb(action="users", page=page - 1))
    if has_next:
        nav.button(text="▶️", callback_data=OwnerCb(action="users", page=page + 1))
    nav.adjust(2)
    kb.attach(nav)

    bottom = InlineKeyboardBuilder()
    bottom.button(text="➕ Добавить вручную", callback_data=OwnerCb(action="user_add"))
    bottom.button(text="⬅️ В меню", callback_data=OwnerCb(action="menu"))
    bottom.adjust(1)
    kb.attach(bottom)
    return kb.as_markup()


def user_card_kb(user) -> InlineKeyboardMarkup:
    uid = user["telegram_id"]
    kb = InlineKeyboardBuilder()
    if user["is_active"]:
        kb.button(text="⛔ Заблокировать", callback_data=UserCb(action="block", uid=uid))
    else:
        kb.button(text="✅ Разблокировать", callback_data=UserCb(action="unblock", uid=uid))
    kb.button(text="🗑 Удалить", callback_data=UserCb(action="delete", uid=uid))
    kb.button(text="⬅️ К пользователям", callback_data=OwnerCb(action="users"))
    kb.adjust(1)
    return kb.as_markup()


def access_request_kb(uid: int) -> InlineKeyboardMarkup:
    """Кнопки под заявкой на доступ (отправляется владельцу)."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Разрешить", callback_data=UserCb(action="allow", uid=uid))
    kb.button(text="❌ Отклонить", callback_data=UserCb(action="deny", uid=uid))
    kb.adjust(2)
    return kb.as_markup()


# ---------- Stats ----------
def stats_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🏆 Топ папок", callback_data=OwnerCb(action="stats_folders"))
    kb.button(text="🏆 Топ пользователей", callback_data=OwnerCb(action="stats_users"))
    kb.button(text="📈 Активность 7 дней", callback_data=OwnerCb(action="stats_7"))
    kb.button(text="📈 Активность 30 дней", callback_data=OwnerCb(action="stats_30"))
    kb.button(text="⬅️ В меню", callback_data=OwnerCb(action="menu"))
    kb.adjust(2, 2, 1)
    return kb.as_markup()


# ---------- Onboarding ----------
def onboarding_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗂 Вставить ссылку на корневую папку", callback_data=OwnerCb(action="set_root"))
    kb.button(text="➡️ Пропустить (позже)", callback_data=OwnerCb(action="menu"))
    kb.adjust(1)
    return kb.as_markup()
