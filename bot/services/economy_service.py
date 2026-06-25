from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from bot.models import UserGroupState, Transaction
from bot.utils.redis_keys import lb_group, lb_global


class EconomyService:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis):
        self.session = session
        self.redis = redis

    async def get_state(self, user_id: int, group_id: int) -> UserGroupState:
        result = await self.session.execute(
            select(UserGroupState).where(
                UserGroupState.user_id == user_id,
                UserGroupState.group_id == group_id,
            )
        )
        return result.scalar_one_or_none()

    async def credit(
        self,
        user_id: int,
        group_id: int,
        amount: int,
        tx_type: str,
        meta: dict = None,
    ) -> UserGroupState:
        state = await self.get_state(user_id, group_id)
        if not state:
            raise ValueError("User state not found")

        state.baa_points += amount
        state.total_earned += max(0, amount)

        tx = Transaction(
            user_id=user_id,
            group_id=group_id,
            type=tx_type,
            amount=amount,
            balance_after=state.baa_points,
            meta=meta,
        )
        self.session.add(tx)
        await self.session.commit()

        # Update leaderboard caches
        await self.redis.zadd(lb_group(group_id), {str(user_id): state.baa_points})
        await self.redis.zadd(lb_global(), {str(user_id): state.baa_points})
        await self.redis.expire(lb_group(group_id), 300)
        await self.redis.expire(lb_global(), 300)

        return state

    async def debit(
        self,
        user_id: int,
        group_id: int,
        amount: int,
        tx_type: str,
        meta: dict = None,
    ) -> UserGroupState:
        state = await self.get_state(user_id, group_id)
        if not state:
            raise ValueError("User state not found")
        if state.baa_points < amount:
            raise ValueError(f"Insufficient balance: {state.baa_points} < {amount}")

        state.baa_points -= amount

        tx = Transaction(
            user_id=user_id,
            group_id=group_id,
            type=tx_type,
            amount=-amount,
            balance_after=state.baa_points,
            meta=meta,
        )
        self.session.add(tx)
        await self.session.commit()

        await self.redis.zadd(lb_group(group_id), {str(user_id): state.baa_points})
        await self.redis.zadd(lb_global(), {str(user_id): state.baa_points})

        return state
