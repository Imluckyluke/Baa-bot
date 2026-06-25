from datetime import datetime, timezone
from typing import List
import math

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from bot.models import OwnedSheep, SheepCatalog, Inventory, UserGroupState
from bot.services.economy_service import EconomyService
from bot.utils.formatters import FOOD_HUNGER_RESTORE


class SheepService:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis):
        self.session = session
        self.redis = redis
        self.economy = EconomyService(session, redis)

    # ── Catalog ──────────────────────────────────────────────────────────────
    async def get_catalog(self) -> List[SheepCatalog]:
        result = await self.session.execute(
            select(SheepCatalog).order_by(SheepCatalog.id)
        )
        return result.scalars().all()

    async def get_catalog_item(self, catalog_id: int) -> SheepCatalog | None:
        return await self.session.get(SheepCatalog, catalog_id)

    # ── Owned sheep ───────────────────────────────────────────────────────────
    async def get_user_sheep(self, user_id: int, group_id: int) -> List[OwnedSheep]:
        result = await self.session.execute(
            select(OwnedSheep).where(
                OwnedSheep.user_id == user_id,
                OwnedSheep.group_id == group_id,
                OwnedSheep.is_alive == True,
            )
        )
        return result.scalars().all()

    async def get_sheep_by_id(self, sheep_id: str, user_id: int) -> OwnedSheep | None:
        result = await self.session.execute(
            select(OwnedSheep).where(
                OwnedSheep.id == sheep_id,
                OwnedSheep.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    # ── Buy ───────────────────────────────────────────────────────────────────
    async def buy_sheep(
        self,
        user_id: int,
        group_id: int,
        catalog_id: int,
        state: UserGroupState,
    ) -> OwnedSheep:
        catalog = await self.get_catalog_item(catalog_id)
        if not catalog:
            raise ValueError("گوسفند یافت نشد.")
        if state.level < catalog.unlock_level:
            raise ValueError(f"LEVEL_REQUIRED:{catalog.unlock_level}")
        if state.baa_points < catalog.cost:
            raise ValueError(f"NO_BALANCE:{state.baa_points}")

        await self.economy.debit(user_id, group_id, catalog.cost, "shop",
                                  meta={"item": "sheep", "catalog_id": catalog_id})

        sheep = OwnedSheep(
            user_id=user_id,
            group_id=group_id,
            catalog_id=catalog_id,
        )
        self.session.add(sheep)
        await self.session.commit()
        await self.session.refresh(sheep)
        return sheep

    # ── Upgrade ───────────────────────────────────────────────────────────────
    def upgrade_cost(self, catalog: SheepCatalog, current_level: int) -> int:
        return int(catalog.upgrade_cost_base * (1.5 ** current_level))

    async def upgrade_sheep(
        self,
        sheep: OwnedSheep,
        user_id: int,
        group_id: int,
        state: UserGroupState,
    ) -> OwnedSheep:
        catalog = sheep.catalog
        if sheep.upgrade_level >= catalog.max_upgrade_level:
            raise ValueError("این گوسفند به حداکثر سطح ارتقا رسیده است.")

        cost = self.upgrade_cost(catalog, sheep.upgrade_level)
        if state.baa_points < cost:
            raise ValueError(f"NO_BALANCE:{state.baa_points}")

        await self.economy.debit(user_id, group_id, cost, "upgrade",
                                  meta={"sheep_id": str(sheep.id)})
        sheep.upgrade_level += 1
        await self.session.commit()
        return sheep

    # ── Income calculation ────────────────────────────────────────────────────
    @staticmethod
    def hunger_factor(hunger_pct: float) -> float:
        h = float(hunger_pct)
        if h < 25:
            return 1.0
        if h < 50:
            return 0.75
        if h < 75:
            return 0.50
        if h < 100:
            return 0.10
        return 0.0

    @staticmethod
    def income_per_min(sheep: OwnedSheep) -> float:
        base = float(sheep.catalog.base_income_per_min)
        upgrade_mult = 1.2 ** sheep.upgrade_level
        h_factor = SheepService.hunger_factor(float(sheep.hunger_pct))
        return base * upgrade_mult * h_factor

    # ── Collect ───────────────────────────────────────────────────────────────
    async def collect_all(self, user_id: int, group_id: int) -> int:
        sheep_list = await self.get_user_sheep(user_id, group_id)
        total = sum(s.pending_income for s in sheep_list)
        if total == 0:
            return 0

        for sheep in sheep_list:
            sheep.pending_income = 0
        await self.session.commit()

        await self.economy.credit(user_id, group_id, total, "collect")
        return total

    # ── Feed ─────────────────────────────────────────────────────────────────
    async def feed_sheep(
        self,
        sheep: OwnedSheep,
        user_id: int,
        group_id: int,
        food_type: str,
    ) -> dict:
        result = await self.session.execute(
            select(Inventory).where(
                Inventory.user_id == user_id,
                Inventory.group_id == group_id,
                Inventory.item_type == food_type,
            )
        )
        inv = result.scalar_one_or_none()
        if not inv or inv.quantity < 1:
            raise ValueError(f"NO_FOOD:{food_type}")

        restore = FOOD_HUNGER_RESTORE.get(food_type, 15)
        old_hunger = float(sheep.hunger_pct)
        sheep.hunger_pct = max(0, old_hunger - restore)
        inv.quantity -= 1
        await self.session.commit()

        return {"food": food_type, "restored": restore, "new_hunger": float(sheep.hunger_pct)}

    # ── Hunger tick (called by scheduler) ─────────────────────────────────────
    async def tick_hunger(self, sheep: OwnedSheep, gain_pct: float):
        sheep.hunger_pct = min(100.0, float(sheep.hunger_pct) + gain_pct)
        sheep.last_hunger_tick = datetime.now(timezone.utc)
        await self.session.commit()

    # ── Income tick (called by scheduler) ─────────────────────────────────────
    async def tick_income(self, sheep: OwnedSheep, minutes: float):
        earned = self.income_per_min(sheep) * minutes
        sheep.pending_income += int(earned)
        sheep.last_income_tick = datetime.now(timezone.utc)
        await self.session.commit()
