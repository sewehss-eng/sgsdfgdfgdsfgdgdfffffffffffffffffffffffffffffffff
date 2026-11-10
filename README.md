# Drive Panel

Telegram-бот — «витрина» Google Диска на **aiogram 3.x**. Показывает материалы
категориями → папками → файлами, выдаёт публичные ссылки в трёх форматах и ведёт
аудит выдач. **Всё управление — изнутри бота** (меню владельца), в `.env` только секреты.

---

## Архитектура

Три слоя. **Сервисы** (`services/`) инкапсулируют внешние зависимости: `DriveService` —
singleton-клиент Google Drive API v3 на Service Account, синхронные вызовы обёрнуты в
`asyncio.to_thread`; `settings_service` даёт типизированный доступ к key-value настройкам
из БД; `template_service` безопасно рендерит `{name}`/`{url}` (посторонние плейсхолдеры не
ломают шаблон); `stats_service` агрегирует статистику. **Данные** (`db/`) — SQLite через
`aiosqlite`: `init.py` держит соединение-singleton, применяет DDL и сид (3 глобальных
шаблона + дефолтные настройки), `repository.py` — все SQL-операции в одном месте.

**Презентация** (`handlers/`, `keyboards/`, `states/`) разделена на три роутера.
`router_user` — категории, навигация, выдача ссылок; защищён `AccessMiddleware`.
`router_owner` — меню владельца с FSM-диалогами; защищён жёстким фильтром `IsOwner`
(`user.id == SUPERADMIN_ID`) и для сообщений, и для callback. `router_common` обрабатывает
`/start`, заявки на доступ и устаревшие кнопки — подключается последним.

**Права** определяются единственным источником — `SUPERADMIN_ID` из `.env`. Ролей в БД нет.
Остальные пользователи работают только в user-части и только при `is_active = True`.
Все callback_data держатся в пределах 64 байт через типизированные `CallbackData`-фабрики.

---

## Дерево проекта

```
drive panel/
├── bot/
│   ├── main.py                     # точка входа: init БД, Drive, middleware, роутеры, polling
│   ├── config.py                   # pydantic-settings — ТОЛЬКО секреты из .env
│   ├── middlewares/
│   │   └── access.py               # AccessMiddleware + IsOwner-фильтр
│   ├── services/
│   │   ├── drive_service.py        # singleton Google Drive API v3 (Service Account)
│   │   ├── settings_service.py     # get/set настроек из БД
│   │   ├── template_service.py     # безопасный рендер {name} и {url}
│   │   └── stats_service.py        # агрегаты статистики
│   ├── db/
│   │   ├── models.py               # DDL-схема + дефолтные settings и шаблоны
│   │   ├── init.py                 # соединение-singleton, применение схемы, сид
│   │   └── repository.py           # все CRUD/SQL-операции
│   ├── handlers/
│   │   ├── common.py               # /start, категории, заявки, unknown callback
│   │   ├── user/
│   │   │   ├── router.py           # router_user
│   │   │   ├── categories.py       # открытие категории
│   │   │   ├── browse.py           # навигация по папкам Drive, пагинация
│   │   │   └── links.py            # 3 режима выдачи ссылки + логирование
│   │   └── owner/
│   │       ├── router.py           # router_owner + IsOwner
│   │       ├── menu.py             # /admin, главное меню, онбординг, cancel FSM
│   │       ├── settings.py         # root folder, page_size, logging
│   │       ├── categories.py       # CRUD категорий (FSM)
│   │       ├── templates.py        # CRUD шаблонов (FSM) + предпросмотр
│   │       ├── users.py            # пользователи, блок/разблок, заявки
│   │       ├── stats.py            # статистика
│   │       ├── audit.py            # журнал действий
│   │       └── onboarding.py       # точка расширения (логика в menu/settings)
│   ├── keyboards/
│   │   ├── callbacks.py            # CallbackData-фабрики (≤64 байт)
│   │   ├── user_kb.py              # клавиатуры user-части
│   │   └── owner_kb.py             # клавиатуры меню владельца
│   └── states/
│       └── owner_states.py         # StatesGroup для FSM-диалогов
├── .env.example
├── requirements.txt
└── README.md
```

---

## Разделение .env / БД

В `.env` — **только** то, что нельзя безопасно хранить в редактируемой из чата БД или
что нужно до подключения к ней:

```
BOT_TOKEN=...                          # токен бота
SUPERADMIN_ID=123456789                # единственный владелец (источник всех прав)
GOOGLE_SERVICE_ACCOUNT_FILE=./sa.json  # путь к JSON сервисного аккаунта
DB_PATH=./bot.db                       # путь к SQLite
```

**Всё остальное — в БД, редактируется из бота** через `/admin`:
`google_root_folder_id`, `page_size`, `template_page_size`, `logging_enabled`,
`history_limit`, категории, шаблоны, доступы пользователей.

> ⚠️ **ID корневой папки задаётся в боте** через `/admin → 🔑 Настройки`, а **не** в `.env`.

---

## Настройка Google Cloud (один раз)

1. **Проект**: [console.cloud.google.com](https://console.cloud.google.com) → создайте проект.
2. **Drive API**: *APIs & Services → Library* → включите **Google Drive API**.
3. **Service Account**: *APIs & Services → Credentials → Create credentials → Service account*.
4. **JSON-ключ**: откройте созданный аккаунт → *Keys → Add key → JSON*. Скачайте файл,
   положите рядом с ботом (путь укажите в `GOOGLE_SERVICE_ACCOUNT_FILE`).
5. **Доступ к папкам**: скопируйте `client_email` из JSON (бот подскажет его в онбординге
   и в Настройках). В Google Drive откройте корневую папку → *Поделиться* → добавьте этот
   email с ролью **Viewer**.
6. **ID корневой папки — НЕ в .env.** Задайте его в боте: `/admin → 🔑 Настройки → Root folder`
   (вставьте ссылку на папку или folder_id, бот сам извлечёт ID и проверит доступ).

---

## Установка и запуск

```bash
# 1. Виртуальное окружение
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 2. Зависимости
pip install -r requirements.txt

# 3. Конфиг
copy .env.example .env         # Windows  (cp для *nix)
#   заполните BOT_TOKEN, SUPERADMIN_ID, GOOGLE_SERVICE_ACCOUNT_FILE

# 4. Положите sa.json рядом (путь = GOOGLE_SERVICE_ACCOUNT_FILE)

# 5. Запуск (из корня проекта — чтобы работал импорт пакета bot)
python -m bot.main
```

При первом `/admin` бот проведёт онбординг: покажет email сервисного аккаунта,
попросит выдать ему доступ к корневой папке и вставить ссылку на неё.

---

## Как расширять

Всё — **только через меню владельца** (`/admin`), код трогать не нужно:

- **Категории**: `📁 Категории → ➕ Добавить` — название, emoji, папка Drive, порядок.
- **Шаблоны**: `✉️ Шаблоны → ➕ Добавить` — многострочный текст с `{name}`/`{url}`,
  привязка к категории или глобально, предпросмотр.
- **Доступы**: `👥 Пользователи` — выдача/блокировка/удаление, обработка заявок.
- **Параметры**: `🔑 Настройки` — root folder, размер страницы, логирование.

Секреты и владелец (`SUPERADMIN_ID`) остаются в `.env` и в боте не редактируются.

---

## SQL-схема и сид

Схема и сид-данные применяются автоматически при старте (`bot/db/init.py`),
исходник — в `bot/db/models.py`:

- `users(telegram_id PK, username, full_name, is_active, created_at, last_seen_at)` — роли нет.
- `categories(id, title, emoji, folder_id, sort_order, is_active, created_at)`.
- `templates(id, title, body, category_id→NULL=глобальный, sort_order, is_active, created_at)`.
- `settings(key PK, value)` — сид: `google_root_folder_id=''`, `page_size=10`,
  `logging_enabled=1`, `template_page_size=10`, `history_limit=50`.
- `link_events(id, user_id, category_id, drive_item_id, drive_item_name, item_type, mode, created_at)`.
- **Дефолтные глобальные шаблоны** (если `templates` пуста): «С пометкой "Материал"»,
  «Простой (заголовок + ссылка)», «Для покупателя» — sort_order 1/2/3.
