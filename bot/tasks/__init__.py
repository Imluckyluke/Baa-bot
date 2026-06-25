import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.db import AsyncSessionLocal
from bot.models import OwnedSheep
from bot.config import settings

logger = logging.getLogger(__name__)


async def hunger_tick():
    """Increase hunger for all alive sheep."""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(OwnedSheep).where(OwnedSheep.is_alive == True)
            )
            sheep_list = result.scalars().all()

            gain = settings.HUNGER_GAIN_RATE_PER_HOUR * settings.HUNGER_TICK_MINUTES / 60

            for sheep in sheep_list:
                sheep.hunger_pct = min(100.0, float(sheep.hunger_pct) + gain)
                sheep.last_hunger_tick = datetime.now(timezone.utc)

            await session.commit()
            logger.debug(f"Hunger tick: updated {len(sheep_list)} sheep")
        except Exception as e:
            logger.error(f"Hunger tick error: {e}")
            await session.rollback()


async def income_tick():
    """Accumulate passive income for all alive sheep."""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(OwnedSheep).where(OwnedSheep.is_alive == True)
            )
            sheep_list = result.scalars().all()

            minutes = settings.INCOME_TICK_MINUTES

            for sheep in sheep_list:
                base = float(sheep.catalog.base_income_per_min)
                upgrade_mult = 1.2 ** sheep.upgrade_level

                h = float(sheep.hunger_pct)
                if h < 25:
                    h_factor = 1.0
                elif h < 50:
                    h_factor = 0.75
                elif h < 75:
                    h_factor = 0.50
                elif h < 100:
                    h_factor = 0.10
                else:
                    h_factor = 0.0

                earned = int(base * upgrade_mult * h_factor * minutes)
                sheep.pending_income += earned
                sheep.last_income_tick = datetime.now(timezone.utc)

            await session.commit()
            logger.debug(f"Income tick: updated {len(sheep_list)} sheep")
        except Exception as e:
            logger.error(f"Income tick error: {e}")
            await session.rollback()


def setup_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        hunger_tick,
        "interval",
        minutes=settings.HUNGER_TICK_MINUTES,
        id="hunger_tick",
        replace_existing=True,
    )
    scheduler.add_job(
        income_tick,
        "interval",
        minutes=settings.INCOME_TICK_MINUTES,
        id="income_tick",
        replace_existing=True,
    )
    return scheduler
