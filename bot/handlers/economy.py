from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from bot.models import User, Group, UserGroupState
from bot.services.gathering_service import GatheringService
from bot.services.bank_service import BankService
from bot.services.daily_service import DailyService
from bot.utils.formatters import fmt_num, fmt_time, FOOD_NAMES

router = Router()


# ── GATHERING ────────────────────────────────────────────────────────────────
@router.message(Command("gather"))
async def cmd_gather(message: Message, session: AsyncSession, redis: aioredis.Redis,
                     user: User, group: Group = None, ugs: UserGroupState = None):
    if not group:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    service = GatheringService(session, redis)
    try:
        res = await service.gather(user.id, group.id, group)
    except ValueError as e:
        err = str(e)
        if err.startswith("COOLDOWN:"):
            secs = int(err.split(":")[1])
            return await message.reply(f"⏳ {fmt_time(secs)} دیگه می‌تونی جمع‌آوری کنی.")
        return await message.reply(f"❌ {err}")

    broken_msg = "\n⚠️ ابزارت شکست! از /buy tool استفاده کن." if res["tool_broken"] else ""
    await message.reply(
        f"🌾 **جمع‌آوری با {res['tool_name']}**\n"
        f"یافتی: {res['loot_name']}\n"
        f"استقامت ابزار: {res['durability'] if res['durability'] >= 0 else '∞'}"
        f"{broken_msg}",
        parse_mode="Markdown"
    )


@router.message(Command("inventory"))
async def cmd_inventory(message: Message, session: AsyncSession, redis: aioredis.Redis,
                        user: User, group: Group = None):
    if not group:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    service = GatheringService(session, redis)
    items = await service.get_inventory(user.id, group.id)

    if not items:
        return await message.reply("🎒 انبارت خالیه. از /gather استفاده کن!")

    lines = ["🎒 **انبار غذا**\n"]
    for item in items:
        name = FOOD_NAMES.get(item.item_type, item.item_type)
        lines.append(f"{name}: **{item.quantity}** عدد")

    await message.reply("\n".join(lines), parse_mode="Markdown")


@router.message(Command("tools"))
async def cmd_tools(message: Message, session: AsyncSession, redis: aioredis.Redis,
                    user: User, group: Group = None):
    if not group:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    service = GatheringService(session, redis)
    tools = await service.get_user_tools(user.id, group.id)

    if not tools:
        return await message.reply("🔧 هیچ ابزاری نداری. از `/buy tool <id>` خرید کن.", parse_mode="Markdown")

    lines = ["🔧 **ابزارهای تو**\n"]
    for t in tools:
        active = "✅ فعال" if t.is_active else ""
        dur = "∞" if t.durability_remaining < 0 else str(t.durability_remaining)
        lines.append(f"{t.catalog.emoji} **{t.catalog.name}** {active}\n   استقامت: {dur}")

    await message.reply("\n".join(lines), parse_mode="Markdown")


# ── BANK ─────────────────────────────────────────────────────────────────────
@router.message(Command("bank"))
async def cmd_bank(message: Message, session: AsyncSession, redis: aioredis.Redis,
                   ugs: UserGroupState = None, group: Group = None):
    if not group or not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    service = BankService(session, redis)
    info = service.get_bank_info(ugs, group)

    await message.reply(
        f"🏦 **بانک BaaBot**\n\n"
        f"💰 موجودی: {fmt_num(info['balance'])} BP\n"
        f"📈 سود معلق: +{fmt_num(info['pending_interest'])} BP\n"
        f"💎 جمع کل: {fmt_num(info['total'])} BP\n"
        f"📊 نرخ سود: {info['rate']*100:.1f}%/ساعت\n\n"
        f"/deposit <مبلغ> — واریز\n"
        f"/withdraw <مبلغ> — برداشت",
        parse_mode="Markdown"
    )


@router.message(Command("deposit"))
async def cmd_deposit(message: Message, session: AsyncSession, redis: aioredis.Redis,
                      user: User, group: Group = None, ugs: UserGroupState = None):
    if not group or not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    args = (message.text or "").split()
    if len(args) < 2:
        return await message.reply("استفاده: `/deposit <مبلغ|all>`", parse_mode="Markdown")

    arg = args[1].lower()
    amount = ugs.baa_points if arg == "all" else int(arg) if arg.isdigit() else None
    if not amount:
        return await message.reply("❌ مبلغ نامعتبر.")

    service = BankService(session, redis)
    try:
        res = await service.deposit(user.id, group.id, amount, ugs, group)
        await message.reply(
            f"✅ **{fmt_num(res['deposited'])} BP** واریز شد!\n"
            f"🏦 موجودی بانک: {fmt_num(res['bank_balance'])} BP",
            parse_mode="Markdown"
        )
    except ValueError as e:
        await message.reply(f"❌ {e}")


@router.message(Command("withdraw"))
async def cmd_withdraw(message: Message, session: AsyncSession, redis: aioredis.Redis,
                       user: User, group: Group = None, ugs: UserGroupState = None):
    if not group or not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    args = (message.text or "").split()
    if len(args) < 2:
        return await message.reply("استفاده: `/withdraw <مبلغ|all>`", parse_mode="Markdown")

    arg = args[1].lower()
    amount = ugs.bank_balance if arg == "all" else int(arg) if arg.isdigit() else None
    if not amount:
        return await message.reply("❌ مبلغ نامعتبر.")

    service = BankService(session, redis)
    try:
        res = await service.withdraw(user.id, group.id, amount, ugs, group)
        await message.reply(
            f"✅ **{fmt_num(res['withdrawn'])} BP** برداشت شد!\n"
            f"🏦 موجودی بانک: {fmt_num(res['bank_balance'])} BP",
            parse_mode="Markdown"
        )
    except ValueError as e:
        await message.reply(f"❌ {e}")


# ── DAILY ─────────────────────────────────────────────────────────────────────
@router.message(Command("daily"))
async def cmd_daily(message: Message, session: AsyncSession, redis: aioredis.Redis,
                    user: User, group: Group = None, ugs: UserGroupState = None):
    if not group or not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    service = DailyService(session, redis)
    try:
        res = await service.claim(user.id, group.id, ugs)
    except ValueError as e:
        err = str(e)
        if err.startswith("COOLDOWN:"):
            secs = int(err.split(":")[1])
            return await message.reply(f"⏳ جایزه روزانه‌ات رو قبلاً گرفتی!\n{fmt_time(secs)} دیگه بیا.")
        return await message.reply(f"❌ {err}")

    bonus_text = ""
    if res["bonus_item"]:
        item_type, qty = res["bonus_item"]
        bonus_text = f"\n🎁 جایزه ویژه: {FOOD_NAMES.get(item_type, item_type)} ×{qty}"

    await message.reply(
        f"🎁 **جایزه روزانه**\n\n"
        f"💰 +{fmt_num(res['reward'])} Baa Point\n"
        f"🔥 استریک: {res['streak']} روز"
        f"{bonus_text}",
        parse_mode="Markdown"
    )
