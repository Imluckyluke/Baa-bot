import random
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from bot.models import CasinoLog, UserGroupState, Group
from bot.services.economy_service import EconomyService
from bot.utils.redis_keys import casino_limit
from bot.config import settings


HOUSE_EDGE = 0.05

SLOT_SYMBOLS = ["🐑", "🌿", "🌾", "🏆", "💎"]
SLOT_WEIGHTS = [40, 30, 20, 8, 2]

SLOT_PAYOUTS = {
    ("💎", "💎", "💎"): 50,
    ("🏆", "🏆", "🏆"): 20,
    ("🌾", "🌾", "🌾"): 10,
    ("🌿", "🌿", "🌿"): 5,
    ("🐑", "🐑", "🐑"): 3,
}


class CasinoService:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis):
        self.session = session
        self.redis = redis
        self.economy = EconomyService(session, redis)

    async def _check_and_deduct_limit(self, user_id: int, group_id: int, amount: int, group: Group):
        key = casino_limit(user_id, group_id)
        spent_raw = await self.redis.get(key)
        spent = int(spent_raw) if spent_raw else 0
        daily_limit = settings.DEFAULT_CASINO_DAILY_LIMIT
        if spent + amount > daily_limit:
            raise ValueError(f"CASINO_LIMIT:{daily_limit}")
        await self.redis.incrby(key, amount)
        await self.redis.expireat(key, int((date.today().toordinal() + 1 - date(1970, 1, 1).toordinal()) * 86400))

    async def _log(self, user_id, group_id, game, bet, payout, meta):
        net = payout - bet
        log = CasinoLog(
            user_id=user_id, group_id=group_id, game=game,
            bet_amount=bet, payout=payout, net=net, meta=meta,
        )
        self.session.add(log)
        await self.session.commit()

    def _validate_bet(self, amount: int, state: UserGroupState):
        if amount < settings.CASINO_MIN_BET:
            raise ValueError(f"INVALID_BET:{settings.CASINO_MIN_BET}")
        if amount > settings.CASINO_MAX_BET:
            raise ValueError(f"INVALID_BET:{settings.CASINO_MAX_BET}")
        if state.baa_points < amount:
            raise ValueError(f"NO_BALANCE:{state.baa_points}")

    async def coinflip(self, user_id, group_id, side: str, bet: int, state, group) -> dict:
        self._validate_bet(bet, state)
        await self._check_and_deduct_limit(user_id, group_id, bet, group)

        result = random.choice(["heads", "tails"])
        won = result == side.lower()
        payout = int(bet * 1.90) if won else 0

        await self.economy.debit(user_id, group_id, bet, "casino", meta={"game": "coinflip"})
        if payout > 0:
            await self.economy.credit(user_id, group_id, payout, "casino", meta={"game": "coinflip"})

        await self._log(user_id, group_id, "coinflip", bet, payout, {"side": side, "result": result})
        return {"result": result, "won": won, "payout": payout, "net": payout - bet}

    async def dice(self, user_id, group_id, guess: int, bet: int, state, group) -> dict:
        if not 1 <= guess <= 6:
            raise ValueError("عدد باید بین ۱ تا ۶ باشد.")
        self._validate_bet(bet, state)
        await self._check_and_deduct_limit(user_id, group_id, bet, group)

        result = random.randint(1, 6)
        won = result == guess
        payout = int(bet * 5.70) if won else 0

        await self.economy.debit(user_id, group_id, bet, "casino", meta={"game": "dice"})
        if payout > 0:
            await self.economy.credit(user_id, group_id, payout, "casino", meta={"game": "dice"})

        await self._log(user_id, group_id, "dice", bet, payout, {"guess": guess, "result": result})
        return {"result": result, "won": won, "payout": payout, "net": payout - bet}

    async def slots(self, user_id, group_id, bet: int, state, group) -> dict:
        self._validate_bet(bet, state)
        await self._check_and_deduct_limit(user_id, group_id, bet, group)

        reels = tuple(random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=3))
        multiplier = SLOT_PAYOUTS.get(reels, 0)

        # Two matching
        if multiplier == 0 and len(set(reels)) == 2:
            multiplier = 0.5

        payout = int(bet * multiplier)

        await self.economy.debit(user_id, group_id, bet, "casino", meta={"game": "slots"})
        if payout > 0:
            await self.economy.credit(user_id, group_id, payout, "casino", meta={"game": "slots"})

        await self._log(user_id, group_id, "slots", bet, payout, {"reels": list(reels)})
        return {"reels": reels, "multiplier": multiplier, "payout": payout, "net": payout - bet}

    async def roulette(self, user_id, group_id, bet_type: str, bet_value, bet: int, state, group) -> dict:
        self._validate_bet(bet, state)
        await self._check_and_deduct_limit(user_id, group_id, bet, group)

        spin = random.randint(0, 36)
        RED = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        is_red = spin in RED
        is_black = spin != 0 and not is_red

        won = False
        payout = 0
        if bet_type == "red" and is_red:
            won = True; payout = int(bet * 1.90)
        elif bet_type == "black" and is_black:
            won = True; payout = int(bet * 1.90)
        elif bet_type == "number" and int(bet_value) == spin:
            won = True; payout = int(bet * 34)

        await self.economy.debit(user_id, group_id, bet, "casino", meta={"game": "roulette"})
        if payout > 0:
            await self.economy.credit(user_id, group_id, payout, "casino", meta={"game": "roulette"})

        await self._log(user_id, group_id, "roulette", bet, payout, {"spin": spin, "bet_type": bet_type})
        return {"spin": spin, "won": won, "payout": payout, "net": payout - bet, "color": "🔴" if is_red else ("⚫" if is_black else "🟢")}
