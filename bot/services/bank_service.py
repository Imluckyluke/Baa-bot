from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from bot.models import UserGroupState, Group
from bot.services.economy_service import EconomyService


MAX_INTEREST_HOURS = 24


class BankService:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis):
        self.session = session
        self.redis = redis
        self.economy = EconomyService(session, redis)

    def compute_interest(self, state: UserGroupState, group: Group) -> int:
        if not state.bank_deposited_at or state.bank_balance == 0:
            return 0
        now = datetime.now(timezone.utc)
        deposited_at = state.bank_deposited_at
        if deposited_at.tzinfo is None:
            deposited_at = deposited_at.replace(tzinfo=timezone.utc)

        hours = (now - deposited_at).total_seconds() / 3600
        hours = min(hours, MAX_INTEREST_HOURS)  # cap at 24h
        rate = float(group.bank_interest_rate)
        interest = int(state.bank_balance * rate * hours)
        return interest

    async def deposit(
        self,
        user_id: int,
        group_id: int,
        amount: int,
        state: UserGroupState,
        group: Group,
    ) -> dict:
        if amount < 100:
            raise ValueError("حداقل واریز ۱۰۰ Baa Point است.")
        if state.baa_points < amount:
            raise ValueError(f"NO_BALANCE:{state.baa_points}")

        # Collect pending interest before depositing more
        interest = self.compute_interest(state, group)
        if interest > 0:
            state.bank_balance += interest

        await self.economy.debit(user_id, group_id, amount, "bank_deposit",
                                  meta={"action": "deposit"})
        state.bank_balance += amount
        state.bank_deposited_at = datetime.now(timezone.utc)
        await self.session.commit()

        return {"deposited": amount, "interest_added": interest, "bank_balance": state.bank_balance}

    async def withdraw(
        self,
        user_id: int,
        group_id: int,
        amount: int,
        state: UserGroupState,
        group: Group,
    ) -> dict:
        # Collect pending interest first
        interest = self.compute_interest(state, group)
        if interest > 0:
            state.bank_balance += interest
            state.bank_deposited_at = datetime.now(timezone.utc)

        total_available = state.bank_balance
        if amount > total_available:
            raise ValueError(f"NO_BALANCE:{total_available}")

        state.bank_balance -= amount
        if state.bank_balance > 0:
            state.bank_deposited_at = datetime.now(timezone.utc)
        else:
            state.bank_deposited_at = None

        await self.economy.credit(user_id, group_id, amount, "bank_withdraw",
                                   meta={"action": "withdraw"})
        await self.session.commit()

        return {"withdrawn": amount, "interest_added": interest, "bank_balance": state.bank_balance}

    def get_bank_info(self, state: UserGroupState, group: Group) -> dict:
        interest = self.compute_interest(state, group)
        return {
            "balance": state.bank_balance,
            "pending_interest": interest,
            "total": state.bank_balance + interest,
            "rate": float(group.bank_interest_rate),
        }
