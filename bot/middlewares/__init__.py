from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, Update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from bot.models.db import AsyncSessionLocal
from bot.models import User, Group, UserGroupState
from bot.utils.redis_keys import rate_key, maintenance
from bot.config import settings


# ── DB Session Middleware ────────────────────────────────────────────────────
class DbMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: Dict[str, Any]):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            return await handler(event, data)


# ── Redis Middleware ─────────────────────────────────────────────────────────
class RedisMiddleware(BaseMiddleware):
    def __init__(self, redis_client):
        self.redis = redis_client

    async def __call__(self, handler, event: TelegramObject, data: Dict[str, Any]):
        data["redis"] = self.redis
        return await handler(event, data)


# ── Maintenance Middleware ───────────────────────────────────────────────────
class MaintenanceMiddleware(BaseMiddleware):
    def __init__(self, redis_client):
        self.redis = redis_client

    async def __call__(self, handler, event: TelegramObject, data: Dict[str, Any]):
        if await self.redis.get(maintenance()):
            if isinstance(event, Message):
                uid = event.from_user.id if event.from_user else None
                if uid and uid in settings.OPERATOR_IDS:
                    return await handler(event, data)
                await event.answer("🔧 BaaBot در حال تعمیر است. به زودی برمی‌گردیم!")
            return
        return await handler(event, data)


# ── Rate Limit Middleware ────────────────────────────────────────────────────
class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, redis_client):
        self.redis = redis_client

    async def __call__(self, handler, event: TelegramObject, data: Dict[str, Any]):
        if not isinstance(event, Message):
            return await handler(event, data)
        user = event.from_user
        if not user:
            return await handler(event, data)

        key = rate_key(user.id)
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, 1)
        if current > 5:  # max 5 messages per second
            return
        return await handler(event, data)


# ── User & Group Registration Middleware ─────────────────────────────────────
class UserRegistrationMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: Dict[str, Any]):
        if not isinstance(event, Message):
            return await handler(event, data)

        session: AsyncSession = data.get("session")
        tg_user = event.from_user
        tg_chat = event.chat

        if not tg_user or not session:
            return await handler(event, data)

        # Upsert user
        user = await session.get(User, tg_user.id)
        if not user:
            user = User(
                id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name or "Unknown",
                last_name=tg_user.last_name,
            )
            session.add(user)
        else:
            user.username = tg_user.username
            user.first_name = tg_user.first_name or "Unknown"
            user.last_name = tg_user.last_name

        # Upsert group (only in group chats)
        if tg_chat.type in ("group", "supergroup"):
            group = await session.get(Group, tg_chat.id)
            if not group:
                group = Group(id=tg_chat.id, title=tg_chat.title or "Group")
                session.add(group)
            else:
                group.title = tg_chat.title or group.title

            # Upsert user_group_state
            result = await session.execute(
                select(UserGroupState).where(
                    UserGroupState.user_id == tg_user.id,
                    UserGroupState.group_id == tg_chat.id,
                )
            )
            state = result.scalar_one_or_none()
            if not state:
                state = UserGroupState(user_id=tg_user.id, group_id=tg_chat.id)
                session.add(state)

            data["group"] = group
            data["ugs"] = state

        data["user"] = user
        await session.commit()

        return await handler(event, data)


# ── Ban Check Middleware ─────────────────────────────────────────────────────
class BanCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: Dict[str, Any]):
        if not isinstance(event, Message):
            return await handler(event, data)
        user: User = data.get("user")
        if user and user.is_banned:
            await event.answer("🚫 شما از استفاده از BaaBot در این گروه محروم شده‌اید.")
            return
        return await handler(event, data)
