import random
from datetime import datetime, timezone
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from bot.models import OwnedTool, ToolCatalog, Inventory, UserGroupState, Group
from bot.utils.redis_keys import gather_cd
from bot.utils.formatters import FOOD_NAMES


class GatheringService:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis):
        self.session = session
        self.redis = redis

    async def get_tool_catalog(self) -> List[ToolCatalog]:
        result = await self.session.execute(select(ToolCatalog).order_by(ToolCatalog.id))
        return result.scalars().all()

    async def get_active_tool(self, user_id: int, group_id: int) -> OwnedTool | None:
        result = await self.session.execute(
            select(OwnedTool).where(
                OwnedTool.user_id == user_id,
                OwnedTool.group_id == group_id,
                OwnedTool.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_tools(self, user_id: int, group_id: int) -> List[OwnedTool]:
        result = await self.session.execute(
            select(OwnedTool).where(
                OwnedTool.user_id == user_id,
                OwnedTool.group_id == group_id,
            )
        )
        return result.scalars().all()

    async def buy_tool(
        self,
        user_id: int,
        group_id: int,
        catalog_id: int,
        state: UserGroupState,
    ) -> OwnedTool:
        from bot.services.economy_service import EconomyService
        economy = EconomyService(self.session, self.redis)

        result = await self.session.execute(
            select(ToolCatalog).where(ToolCatalog.id == catalog_id)
        )
        catalog = result.scalar_one_or_none()
        if not catalog:
            raise ValueError("ابزار یافت نشد.")
        if state.level < catalog.unlock_level:
            raise ValueError(f"LEVEL_REQUIRED:{catalog.unlock_level}")
        if state.baa_points < catalog.cost:
            raise ValueError(f"NO_BALANCE:{state.baa_points}")

        await economy.debit(user_id, group_id, catalog.cost, "shop",
                            meta={"item": "tool", "catalog_id": catalog_id})

        tool = OwnedTool(
            user_id=user_id,
            group_id=group_id,
            catalog_id=catalog_id,
            durability_remaining=catalog.max_durability,
        )
        self.session.add(tool)
        await self.session.commit()
        await self.session.refresh(tool)
        return tool

    async def equip_tool(self, tool: OwnedTool, user_id: int, group_id: int):
        # Deactivate all other tools
        all_tools = await self.get_user_tools(user_id, group_id)
        for t in all_tools:
            t.is_active = False
        tool.is_active = True
        await self.session.commit()

    def _roll_loot(self, yield_table: list) -> str:
        items = [e["type"] for e in yield_table]
        weights = [e["weight"] for e in yield_table]
        return random.choices(items, weights=weights, k=1)[0]

    async def gather(
        self,
        user_id: int,
        group_id: int,
        group: Group,
    ) -> dict:
        remaining = await self.redis.ttl(gather_cd(user_id, group_id))
        if remaining > 0:
            raise ValueError(f"COOLDOWN:{remaining}")

        tool = await self.get_active_tool(user_id, group_id)
        if not tool:
            # Auto-equip bare hands (catalog_id=1)
            bare = OwnedTool(
                user_id=user_id,
                group_id=group_id,
                catalog_id=1,
                durability_remaining=-1,
                is_active=True,
            )
            self.session.add(bare)
            await self.session.commit()
            await self.session.refresh(bare)
            tool = bare

        catalog = tool.catalog
        loot_type = self._roll_loot(catalog.yield_table)

        # Reduce durability
        if tool.durability_remaining > 0:
            tool.durability_remaining -= 1
            if tool.durability_remaining == 0:
                tool.is_active = False
                # Auto-switch back to bare hands next gather

        # Add to inventory
        result = await self.session.execute(
            select(Inventory).where(
                Inventory.user_id == user_id,
                Inventory.group_id == group_id,
                Inventory.item_type == loot_type,
            )
        )
        inv = result.scalar_one_or_none()
        if inv:
            inv.quantity += 1
        else:
            inv = Inventory(user_id=user_id, group_id=group_id, item_type=loot_type, quantity=1)
            self.session.add(inv)

        await self.session.commit()

        # Set cooldown
        await self.redis.set(gather_cd(user_id, group_id), 1, ex=group.gathering_cooldown_sec)

        return {
            "loot": loot_type,
            "loot_name": FOOD_NAMES.get(loot_type, loot_type),
            "tool_name": catalog.name,
            "durability": tool.durability_remaining,
            "tool_broken": tool.durability_remaining == 0,
        }

    async def get_inventory(self, user_id: int, group_id: int) -> List[Inventory]:
        result = await self.session.execute(
            select(Inventory).where(
                Inventory.user_id == user_id,
                Inventory.group_id == group_id,
                Inventory.quantity > 0,
            )
        )
        return result.scalars().all()
