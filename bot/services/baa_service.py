from datetime import datetime, timezone
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Group, UserGroupState
from bot.services.economy_service import EconomyService
from bot.services.level_service import LevelService
from bot.utils.redis_keys import baa_cd


class BaaService:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis):
        self.session = session
        self.redis = redis
        self.economy = EconomyService(session, redis)
        self.levels = LevelService(session)

    async def check_cooldown(self, user_id: int, group_id: int) -> int:
        """Returns remaining cooldown in seconds, or 0 if ready."""
        ttl = await self.redis.ttl(baa_cd(user_id, group_id))
        return max(0, ttl)

    async def claim(
        self,
        user_id: int,
        group_id: int,
        group: Group,
        state: UserGroupState,
    ) -> dict:
        """
        Processes a baa claim.
        Returns result dict with earned, level_up info, cooldown_set.
        Raises ValueError if on cooldown.
        """
        remaining = await self.check_cooldown(user_id, group_id)
        if remaining > 0:
            raise ValueError(f"COOLDOWN:{remaining}")

        reward = group.baa_base_reward
        xp_gain = group.baa_xp_reward

        # Credit points
        state = await self.economy.credit(
            user_id, group_id, reward, "baa",
            meta={"xp": xp_gain}
        )

        # Award XP
        leveled_up, new_level = await self.levels.award_xp(state, xp_gain)

        # Update baa count
        state.total_baa_count += 1
        state.last_baa_at = datetime.now(timezone.utc)
        await self.session.commit()

        # Set cooldown
        await self.redis.set(baa_cd(user_id, group_id), 1, ex=group.baa_cooldown_sec)

        return {
            "earned": reward,
            "xp_gained": xp_gain,
            "balance": state.baa_points,
            "leveled_up": leveled_up,
            "new_level": new_level,
            "total_baa": state.total_baa_count,
        }
