"""
DDL-схема БД (SQLite) + дефолтные сид-данные.

Таблицы:
  users       — пользователи и их доступ (роли нет, админ один = SUPERADMIN_ID)
  categories  — категории (витрина папок Google Drive)
  templates   — шаблоны готового текста ({name}, {url})
  settings    — key-value настройки, редактируемые из бота
  link_events — аудит выдач ссылок
"""
from __future__ import annotations

# --- DDL ---------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id   INTEGER PRIMARY KEY,
    username      TEXT,
    full_name     TEXT,
    is_active     INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    last_seen_at  TEXT
);

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    emoji       TEXT    NOT NULL DEFAULT '',
    folder_id   TEXT    NOT NULL DEFAULT '',   -- пусто у контейнера подкатегорий
    parent_id   INTEGER,                        -- NULL = корневая категория
    kind        TEXT    NOT NULL DEFAULT 'folder', -- 'folder' | 'container'
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE CASCADE
);

-- Кастомные значения плейсхолдеров категории/подкатегории.
-- Задаются один раз, подставляются в шаблоны автоматически.
CREATE TABLE IF NOT EXISTS category_vars (
    category_id INTEGER NOT NULL,
    key         TEXT    NOT NULL,   -- этап | предмет | год | регион | класс ...
    value       TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (category_id, key),
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    body        TEXT    NOT NULL,
    category_id INTEGER,                 -- NULL = глобальный шаблон
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS link_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER,
    category_id     INTEGER,
    drive_item_id   TEXT    NOT NULL,
    drive_item_name TEXT    NOT NULL,
    item_type       TEXT    NOT NULL,   -- folder | file
    mode            TEXT    NOT NULL,   -- button | raw | template:<id>
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id)     REFERENCES users(telegram_id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE INDEX IF NOT EXISTS idx_link_events_user     ON link_events(user_id);
CREATE INDEX IF NOT EXISTS idx_link_events_item     ON link_events(drive_item_id);
CREATE INDEX IF NOT EXISTS idx_link_events_created  ON link_events(created_at);
CREATE INDEX IF NOT EXISTS idx_categories_active    ON categories(is_active, sort_order);
CREATE INDEX IF NOT EXISTS idx_templates_category   ON templates(category_id, sort_order);
"""

# --- Дефолтные настройки -----------------------------------------------------

DEFAULT_SETTINGS = {
    "google_root_folder_id": "",   # задаётся владельцем через /admin
    "page_size": "10",
    "logging_enabled": "1",
    "template_page_size": "10",
    "history_limit": "50",
}

# --- Кастомные плейсхолдеры ---------------------------------------------------
# Фиксированного списка НЕТ: бот сам находит {...} в тексте шаблонов.
# {name} — имя папки, {url} — ссылка. Любые другие {что-угодно} — ваши,
# значения задаются на категории/подкатегории (меню владельца → «🏷 Значения»)
# и наследуются вниз.

# --- Дефолтные (глобальные) шаблоны ------------------------------------------
# Порядок sort_order. category_id = NULL (глобальные).

DEFAULT_TEMPLATES = [
    {
        "title": 'С пометкой "Материал"',
        "body": "{name}\n🔗 Материал: {url}",
        "sort_order": 1,
    },
    {
        "title": "Простой (заголовок + ссылка)",
        "body": "{name}\n{url}",
        "sort_order": 2,
    },
    {
        "title": "Для покупателя",
        "body": (
            "Здравствуйте! Ваш заказ «{name}» готов.\n"
            "📥 Скачать: {url}\n\n"
            "Если возникнут вопросы — пишите."
        ),
        "sort_order": 3,
    },
    {
        # {name} = имя папки (предмет), {работа}/{регион} — ваши значения.
        "title": "Олимпиада (работа/регион)",
        "body": "{работа}: {name} регион ({регион})\n{url}",
        "sort_order": 4,
    },
]

