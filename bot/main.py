import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
import redis.asyncio as aioredis

from bot.config import settings
from bot.middlewares import (
    DbMiddleware,
    RedisMiddleware,
    RateLimitMiddleware,
    UserRegistrationMiddleware,
    BanCheckMiddleware,
    MaintenanceMiddleware,
)
from bot.handlers import baa, sheep, casino, economy, social, admin
from bot.tasks import setup_scheduler

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    storage = RedisStorage(redis_client)

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    dp = Dispatcher(storage=storage)

    # ── Middlewares ─────────────────────────────────────────────────────────
    dp.message.middleware(MaintenanceMiddleware(redis_client))
    dp.message.middleware(RateLimitMiddleware(redis_client))
    dp.message.middleware(DbMiddleware())
    dp.message.middleware(RedisMiddleware(redis_client))
    dp.message.middleware(UserRegistrationMiddleware())
    dp.message.middleware(BanCheckMiddleware())

    # ── Routers ─────────────────────────────────────────────────────────────
    dp.include_router(baa.router)
    dp.include_router(sheep.router)
    dp.include_router(casino.router)
    dp.include_router(economy.router)
    dp.include_router(social.router)
    dp.include_router(admin.router)

    # ── Background tasks ────────────────────────────────────────────────────
    scheduler = setup_scheduler()

    async def on_startup():
        scheduler.start()
        logger.info("BaaBot started! 🐑")
        for op_id in settings.OPERATOR_IDS:
            try:
                await bot.send_message(op_id, "🐑 BaaBot راه‌اندازی شد!")
            except Exception:
                pass

    async def on_shutdown():
        scheduler.shutdown(wait=False)
        await redis_client.aclose()
        logger.info("BaaBot stopped.")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # ── Polling (Railway) ───────────────────────────────────────────────────
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
