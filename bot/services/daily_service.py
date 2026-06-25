from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from bot.models import UserGroupState
from bot.services.economy_service import EconomyService


STREAK_REWARDS = [200, 250, 350, 500, 750, 1000, 2000]
STREAK_BONUS_ITEMS = {
    3: ("dried_grass", 3),
    5: ("fresh_hay", 2),
    7: ("alpine_clover", 1),
}


class DailyService:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis):
        self.session = session
        self.redis = redis
        self.economy = EconomyService(session, redis)

    async def claim(self, user_id: int, group_id: int, state: UserGroupState) -> dict:
        now = datetime.now(timezone.utc)

        if state.last_daily_at:
            last = state.last_daily_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            hours_since = (now - last).total_seconds() / 3600
            if hours_since < 20:
                remaining = int((20 * 3600) - (now - last).total_seconds())
                raise ValueError(f"COOLDOWN:{remaining}")
            if hours_since > 48:
                state.daily_streak = 0

        state.daily_streak += 1
        streak = state.daily_streak
        idx = min((streak - 1) % 7, 6)
        base_reward = STREAK_REWARDS[idx]

        # Weekly bonus after day 7
        bonus_multiplier = 1 + (0.10 * ((streak - 1) // 7))
        reward = int(base_reward * bonus_multiplier)

        state.last_daily_at = now
        await self.session.commit()

        await self.economy.credit(user_id, group_id, reward, "daily",
                                   meta={"streak": streak})

        # Bonus item for certain streaks
        bonus_item = STREAK_BONUS_ITEMS.get((streak - 1) % 7 + 1)

        return {
            "reward": reward,
            "streak": streak,
            "bonus_item": bonus_item,
        }
