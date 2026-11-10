"""
CallbackData-фабрики. Все callback_data держим ≤ 64 байт.
drive_item_id Google Drive — ~33 символа, помещаемся.
"""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class CompatibleCallbackData(CallbackData, prefix="compat"):
    """Обход ошибки aiogram 3.13.1 с default="" при unpack.

    Библиотека считает любое поле с default nullable и превращает "" в
    None, даже если тип поля — str. Сохраняем строковые defaults, чтобы
    существующие кнопки (например own:categories::0) проходили фильтры.
    """

    @classmethod
    def unpack(cls, value: str):
        prefix, *parts = value.split(cls.__separator__)
        fields = cls.model_fields
        if len(parts) != len(fields):
            raise TypeError("Неверное количество полей callback")
        if prefix != cls.__prefix__:
            raise ValueError("Неверный префикс callback")
        payload = {}
        for (name, field), part in zip(fields.items(), parts):
            if part == "" and not field.is_required():
                payload[name] = field.get_default(call_default_factory=True)
            else:
                payload[name] = part
        return cls(**payload)



class CategoryCb(CallbackData, prefix="cat"):
    """Открыть категорию."""
    id: int


class FolderCb(CallbackData, prefix="fld"):
    """Навигация внутри Drive. cat — id категории (для аудита), fid — folder_id."""
    cat: int
    fid: str
    page: int = 0


class ItemCb(CallbackData, prefix="itm"):
    """Выбор конкретного элемента (меню ссылок)."""
    cat: int
    iid: str
    t: str  # f=folder, d=file


class LinkModeCb(CallbackData, prefix="lm"):
    """Режим выдачи ссылки. m: button|raw|tpl."""
    cat: int
    iid: str
    t: str
    m: str


class TemplateCb(CallbackData, prefix="tpl"):
    """Выбор шаблона при выдаче 'с готовым текстом'."""
    cat: int
    iid: str
    t: str
    tid: int


class PageCb(CallbackData, prefix="pg"):
    """Пагинация категории/папки (used inside FolderCb page). Generic list page."""
    scope: str
    ref: str
    page: int


class NavCb(CallbackData, prefix="nav"):
    """Навигационные кнопки: home (категории), back и т.п."""
    action: str  # home | noop


# ----- Owner -----
class OwnerCb(CompatibleCallbackData, prefix="own"):
    """Главное меню владельца и переходы. action — раздел/команда."""
    action: str
    arg: str = ""
    page: int = 0


class UserCb(CallbackData, prefix="usr"):
    """Действия над пользователем."""
    action: str  # open | block | unblock | delete | allow | deny
    uid: int
    page: int = 0


class OwnerCatCb(CompatibleCallbackData, prefix="ocat"):
    """CRUD категорий/подкатегорий в меню владельца.

    actions: list(показать список детей parent) | open | add | add_sub |
             del | toggle | field | tpls | kind | vars | var_set | var_clear
    id — id категории; arg — вспомогательное (parent_id, kind, ключ var).
    """
    action: str
    id: int = 0
    field: str = ""
    arg: str = ""


class OwnerTplCb(CompatibleCallbackData, prefix="otpl"):
    """CRUD шаблонов в меню владельца."""
    action: str  # open | add | edit | del | toggle | preview | field | bind
    id: int = 0
    field: str = ""
    arg: str = ""
