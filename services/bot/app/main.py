import logging

from aiogram import Bot, Dispatcher

from app.clients.api_client import GymApiClient
from app.core.config import settings
from app.handlers import coaches_router, dynamic_exercise_router, fallback_router, reserved_router


async def run() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN no está configurado.")

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()

    api_client = GymApiClient(
        base_url=settings.api_base_url,
        timeout_seconds=settings.api_timeout_seconds,
        api_key=settings.api_secret_key,
    )
    dp["api_client"] = api_client

    dp.include_router(reserved_router)
    dp.include_router(coaches_router)
    dp.include_router(dynamic_exercise_router)
    dp.include_router(fallback_router)

    logger.info("GymOps Telegram bot iniciado.")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await api_client.close()
        await bot.session.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
