from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from bot.models import User, Group, UserGroupState
from bot.services.casino_service import CasinoService
from bot.utils.formatters import fmt_num

router = Router()


def parse_bet(arg: str, balance: int) -> int:
    arg = arg.lower().strip()
    if arg == "all":
        return balance
    if arg == "half":
        return balance // 2
    try:
        return int(arg)
    except ValueError:
        raise ValueError("مبلغ شرط‌بندی نامعتبر است.")


@router.message(Command("casino"))
async def cmd_casino(message: Message, ugs: UserGroupState = None):
    if not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")
    await message.reply(
        "🎰 **کازینوی BaaBot**\n\n"
        "🪙 /coinflip <heads|tails> <مبلغ>\n"
        "🎲 /dice <1-6> <مبلغ>\n"
        "🎰 /slots <مبلغ>\n"
        "🎡 /roulette <red|black|عدد> <مبلغ>\n\n"
        f"💰 موجودی تو: {fmt_num(ugs.baa_points)} BP\n"
        "⚠️ مسئولانه بازی کن!",
        parse_mode="Markdown"
    )


@router.message(Command("coinflip"))
async def cmd_coinflip(message: Message, session: AsyncSession, redis: aioredis.Redis,
                       user: User, group: Group = None, ugs: UserGroupState = None):
    if not group or not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    args = (message.text or "").split()
    if len(args) < 3:
        return await message.reply("استفاده: `/coinflip <heads|tails> <مبلغ>`", parse_mode="Markdown")

    side = args[1].lower()
    if side not in ("heads", "tails"):
        return await message.reply("❌ فقط `heads` یا `tails` قبول می‌شه.", parse_mode="Markdown")

    try:
        bet = parse_bet(args[2], ugs.baa_points)
    except ValueError as e:
        return await message.reply(f"❌ {e}")

    service = CasinoService(session, redis)
    try:
        res = await service.coinflip(user.id, group.id, side, bet, ugs, group)
    except ValueError as e:
        return await message.reply(f"❌ {e}")

    emoji = "✅" if res["won"] else "❌"
    side_fa = "شیر" if res["result"] == "heads" else "خط"
    await message.reply(
        f"🪙 **سکه انداخته شد!**\n"
        f"نتیجه: {side_fa}\n"
        f"{emoji} {'بردی' if res['won'] else 'باختی'}: {fmt_num(abs(res['net']))} BP",
        parse_mode="Markdown"
    )


@router.message(Command("dice"))
async def cmd_dice(message: Message, session: AsyncSession, redis: aioredis.Redis,
                   user: User, group: Group = None, ugs: UserGroupState = None):
    if not group or not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    args = (message.text or "").split()
    if len(args) < 3:
        return await message.reply("استفاده: `/dice <1-6> <مبلغ>`", parse_mode="Markdown")

    try:
        guess = int(args[1])
        bet = parse_bet(args[2], ugs.baa_points)
    except (ValueError, IndexError):
        return await message.reply("❌ ورودی نامعتبر.")

    service = CasinoService(session, redis)
    try:
        res = await service.dice(user.id, group.id, guess, bet, ugs, group)
    except ValueError as e:
        return await message.reply(f"❌ {e}")

    emoji = "✅" if res["won"] else "❌"
    dice_emojis = ["", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
    await message.reply(
        f"🎲 **تاس انداخته شد!**\n"
        f"نتیجه: {dice_emojis[res['result']]}\n"
        f"{emoji} {'بردی' if res['won'] else 'باختی'}: {fmt_num(abs(res['net']))} BP",
        parse_mode="Markdown"
    )


@router.message(Command("slots"))
async def cmd_slots(message: Message, session: AsyncSession, redis: aioredis.Redis,
                    user: User, group: Group = None, ugs: UserGroupState = None):
    if not group or not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    args = (message.text or "").split()
    if len(args) < 2:
        return await message.reply("استفاده: `/slots <مبلغ>`", parse_mode="Markdown")

    try:
        bet = parse_bet(args[1], ugs.baa_points)
    except ValueError as e:
        return await message.reply(f"❌ {e}")

    service = CasinoService(session, redis)
    try:
        res = await service.slots(user.id, group.id, bet, ugs, group)
    except ValueError as e:
        return await message.reply(f"❌ {e}")

    r1, r2, r3 = res["reels"]
    won = res["net"] > 0
    await message.reply(
        f"🎰 **اسلات**\n"
        f"[ {r1} | {r2} | {r3} ]\n"
        f"{'✅ بردی' if won else '❌ باختی'}: {fmt_num(abs(res['net']))} BP\n"
        f"ضریب: ×{res['multiplier']}",
        parse_mode="Markdown"
    )


@router.message(Command("roulette"))
async def cmd_roulette(message: Message, session: AsyncSession, redis: aioredis.Redis,
                       user: User, group: Group = None, ugs: UserGroupState = None):
    if not group or not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    args = (message.text or "").split()
    if len(args) < 3:
        return await message.reply(
            "استفاده: `/roulette <red|black|عدد> <مبلغ>`",
            parse_mode="Markdown"
        )

    bet_type_raw = args[1].lower()
    if bet_type_raw in ("red", "black"):
        bet_type = bet_type_raw
        bet_value = None
    else:
        try:
            bet_value = int(bet_type_raw)
            if not 0 <= bet_value <= 36:
                raise ValueError
            bet_type = "number"
        except ValueError:
            return await message.reply("❌ انتخاب باید `red`، `black` یا عددی بین 0-36 باشه.", parse_mode="Markdown")

    try:
        bet = parse_bet(args[2], ugs.baa_points)
    except ValueError as e:
        return await message.reply(f"❌ {e}")

    service = CasinoService(session, redis)
    try:
        res = await service.roulette(user.id, group.id, bet_type, bet_value, bet, ugs, group)
    except ValueError as e:
        return await message.reply(f"❌ {e}")

    await message.reply(
        f"🎡 **رولت**\n"
        f"نتیجه: {res['color']} **{res['spin']}**\n"
        f"{'✅ بردی' if res['won'] else '❌ باختی'}: {fmt_num(abs(res['net']))} BP",
        parse_mode="Markdown"
    )
