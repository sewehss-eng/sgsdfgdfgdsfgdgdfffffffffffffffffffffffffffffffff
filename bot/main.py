"""
Точка входа. Инициализация БД, Drive singleton, middleware, роутеры, polling.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.db.init import close_db, init_db
from bot.middlewares.access import AccessMiddleware
from bot.services.drive_service import DriveService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("drive_panel")


def build_dispatcher() -> Dispatcher:
    # Проверяем разбор реальных команд до начала polling: при старом
    # callbacks.py бот не должен молча запускаться с неработающим меню.
    from bot.keyboards.callbacks import OwnerCb, OwnerCatCb, OwnerTplCb

    for factory, raw in (
        (OwnerCb, "own:settings::0"),
        (OwnerCb, "own:templates::0"),
        (OwnerCatCb, "ocat:open:1::"),
        (OwnerTplCb, "otpl:open:1::"),
    ):
        try:
            factory.unpack(raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Не работает разбор кнопок. Обновите bot/keyboards/callbacks.py "
                "в той копии проекта, из которой запускается бот."
            ) from exc
    log.info("CALLBACK_FIX_V1: проверка кнопок пройдена; main=%s", __file__)

    dp = Dispatcher(storage=MemoryStorage())

    # Роутеры импортируем здесь, чтобы хендлеры зарегистрировались на своих роутерах.
    from bot.handlers.owner.router import router_owner
    from bot.handlers.user.router import router_user
    from bot.handlers.common import router_common

    # Подтягиваем модули-хендлеры (регистрация декораторов).
    import bot.handlers.owner.menu       # noqa: F401
    import bot.handlers.owner.settings   # noqa: F401
    import bot.handlers.owner.categories # noqa: F401
    import bot.handlers.owner.templates  # noqa: F401
    import bot.handlers.owner.users      # noqa: F401
    import bot.handlers.owner.stats      # noqa: F401
    import bot.handlers.owner.audit      # noqa: F401
    import bot.handlers.user.categories  # noqa: F401
    import bot.handlers.user.browse      # noqa: F401
    import bot.handlers.user.links       # noqa: F401

    # Access middleware — на user и common (owner защищён IsOwner-фильтром).
    access = AccessMiddleware()
    router_user.message.middleware(access)
    router_user.callback_query.middleware(access)
    router_common.message.middleware(access)
    router_common.callback_query.middleware(access)

    # Порядок: owner (жёсткий фильтр) → user → common (common ловит unknown callback).
    dp.include_router(router_owner)
    dp.include_router(router_user)
    dp.include_router(router_common)
    for router in (router_owner, router_user, router_common):
        log.info(
            "Router %s: message_handlers=%d callback_handlers=%d",
            router.name,
            len(router.message.handlers),
            len(router.callback_query.handlers),
        )
    return dp


async def main() -> None:
    await init_db()
    DriveService.get()  # singleton + ранняя валидация service account

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()

    log.info("Бот запущен. SUPERADMIN_ID=%s", settings.superadmin_id)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановка бота.")
