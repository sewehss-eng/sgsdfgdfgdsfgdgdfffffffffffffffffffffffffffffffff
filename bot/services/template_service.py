"""
template_service — безопасный рендер шаблонов.

{name} — имя папки, {url} — ссылка. Любые другие {что-угодно} — ваши
плейсхолдеры: бот находит их в тексте, значения задаются на категории.
Неизвестные {...} при рендере остаются как есть (не бросают KeyError).
"""
from __future__ import annotations

import re

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Zа-яА-ЯёЁ_][\w]*)\}")


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def find_placeholders(body: str) -> list[str]:
    """Все плейсхолдеры в шаблоне (без дублей, порядок сохранён)."""
    seen: list[str] = []
    for m in _PLACEHOLDER_RE.finditer(body):
        k = m.group(1)
        if k not in seen:
            seen.append(k)
    return seen


def custom_placeholders(body: str) -> list[str]:
    """Кастомные плейсхолдеры (кроме name/url)."""
    return [p for p in find_placeholders(body) if p not in ("name", "url")]


def validate_body(body: str) -> bool:
    """body обязан содержать оба обязательных плейсхолдера."""
    return "{name}" in body and "{url}" in body


def render(body: str, name: str, url: str, extra: dict[str, str] | None = None) -> str:
    """
    Безопасный рендер: подставляет {name}, {url} и любые кастомные значения
    из extra. Неизвестные {...} остаются как есть.
    """
    values = {"name": name, "url": url}
    if extra:
        values.update(extra)
    return body.format_map(_SafeDict(values))


# Для предпросмотра в меню владельца
PREVIEW_NAME = "Пример названия папки"
PREVIEW_URL = "https://drive.google.com/drive/folders/EXAMPLE"


def preview(body: str, extra: dict[str, str] | None = None) -> str:
    """
    Предпросмотр. Кастомные плейсхолдеры, для которых не передано значение,
    показываются как [имя] — чтобы было видно структуру.
    """
    custom = {ph: f"[{ph}]" for ph in custom_placeholders(body)}
    if extra:
        custom.update({k: v for k, v in extra.items() if v})
    return render(body, PREVIEW_NAME, PREVIEW_URL, custom)
