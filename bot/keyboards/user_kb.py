"""Клавиатуры пользовательской части."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.callbacks import (
    CategoryCb,
    FolderCb,
    ItemCb,
    LinkModeCb,
    NavCb,
    TemplateCb,
)
from bot.services.drive_service import FOLDER_MIME


def categories_kb(categories, parent_id: int | None = None) -> InlineKeyboardMarkup:
    """Список категорий/подкатегорий. parent_id — для кнопки «Назад» из подкатегорий."""
    kb = InlineKeyboardBuilder()
    for c in categories:
        emoji = (c["emoji"] + " ") if c["emoji"] else "📁 "
        kb.button(text=f"{emoji}{c['title']}", callback_data=CategoryCb(id=c["id"]))
    kb.adjust(1)
    # Если это уровень подкатегорий — добавим навигацию наверх.
    if parent_id is not None:
        kb.row(
            InlineKeyboardButton(
                text="⬅️ Назад", callback_data=CategoryCb(id=parent_id).pack()
            ),
            InlineKeyboardButton(
                text="🏠 Категории", callback_data=NavCb(action="home").pack()
            ),
        )
    return kb.as_markup()


def browse_kb(
    items: list[dict],
    category_id: int,
    current_folder: str,
    parent_folder: str | None,
    page: int,
    page_size: int,
) -> InlineKeyboardMarkup:
    """Список подпапок и файлов + навигация + пагинация."""
    kb = InlineKeyboardBuilder()

    total = len(items)
    start = page * page_size
    chunk = items[start : start + page_size]

    for it in chunk:
        is_folder = it["mimeType"] == FOLDER_MIME
        if is_folder:
            kb.row(
                InlineKeyboardButton(
                    text=f"📂 {it['name']}",
                    callback_data=FolderCb(
                        cat=category_id, fid=it["id"], page=0
                    ).pack(),
                )
            )
        else:
            kb.row(
                InlineKeyboardButton(
                    text=f"📄 {it['name']}",
                    callback_data=ItemCb(
                        cat=category_id, iid=it["id"], t="d"
                    ).pack(),
                )
            )

    # Пагинация
    if total > page_size:
        nav_row: list[InlineKeyboardButton] = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=FolderCb(
                        cat=category_id, fid=current_folder, page=page - 1
                    ).pack(),
                )
            )
        nav_row.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{(total - 1) // page_size + 1}",
                callback_data=NavCb(action="noop").pack(),
            )
        )
        if start + page_size < total:
            nav_row.append(
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=FolderCb(
                        cat=category_id, fid=current_folder, page=page + 1
                    ).pack(),
                )
            )
        kb.row(*nav_row)

    # Кнопка «получить ссылку на текущую папку»
    kb.row(
        InlineKeyboardButton(
            text="🔗 Ссылка на эту папку",
            callback_data=ItemCb(cat=category_id, iid=current_folder, t="f").pack(),
        )
    )

    # Навигация назад/домой
    bottom: list[InlineKeyboardButton] = []
    if parent_folder:
        bottom.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=FolderCb(
                    cat=category_id, fid=parent_folder, page=0
                ).pack(),
            )
        )
    bottom.append(
        InlineKeyboardButton(text="🏠 Категории", callback_data=NavCb(action="home").pack())
    )
    kb.row(*bottom)

    return kb.as_markup()


def link_modes_kb(category_id: int, item_id: str, item_type: str) -> InlineKeyboardMarkup:
    """Три режима выдачи ссылки."""
    kb = InlineKeyboardBuilder()
    kb.button(
        text="🔗 Ссылка кнопкой",
        callback_data=LinkModeCb(cat=category_id, iid=item_id, t=item_type, m="button"),
    )
    kb.button(
        text="📋 Ссылка текстом",
        callback_data=LinkModeCb(cat=category_id, iid=item_id, t=item_type, m="raw"),
    )
    kb.button(
        text="✉️ С готовым текстом",
        callback_data=LinkModeCb(cat=category_id, iid=item_id, t=item_type, m="tpl"),
    )
    kb.button(text="🏠 Категории", callback_data=NavCb(action="home"))
    kb.adjust(1)
    return kb.as_markup()


def templates_choose_kb(
    templates, category_id: int, item_id: str, item_type: str
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in templates:
        kb.button(
            text=t["title"],
            callback_data=TemplateCb(
                cat=category_id, iid=item_id, t=item_type, tid=t["id"]
            ),
        )
    kb.button(text="🏠 Категории", callback_data=NavCb(action="home"))
    kb.adjust(1)
    return kb.as_markup()


def open_link_button_kb(name: str, url: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=f"Открыть «{name}»", url=url)
    return kb.as_markup()
