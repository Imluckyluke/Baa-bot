import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from bot.models import User, Group, UserGroupState
from bot.services.baa_service import BaaService
from bot.utils.formatters import fmt_num, xp_bar, fmt_time
from bot.services.level_service import xp_in_current_level, xp_for_level

router = Router()

BAA_PATTERN = re.compile(r"^b+a+a+\s*$", re.IGNORECASE)


async def _process_baa(message: Message, session: AsyncSession, redis: aioredis.Redis,
                        user: User, group: Group, ugs: UserGroupState):
    if not group:
        return  # Only works in groups

    service = BaaService(session, redis)
    try:
        result = await service.claim(user.id, group.id, group, ugs)
    except ValueError as e:
        err = str(e)
        if err.startswith("COOLDOWN:"):
            secs = int(err.split(":")[1])
            await message.reply(
                f"⏳ گوسفندهات هنوز آماده نیستن!\n"
                f"⏱ {fmt_time(secs)} دیگه صبر کن."
            )
        return

    xp_in_lvl, xp_needed = xp_in_current_level(ugs.xp)
    bar = xp_bar(xp_in_lvl, xp_needed)

    text = (
        f"🐑 **بع!**\n"
        f"➕ +{fmt_num(result['earned'])} Baa Point\n"
        f"💰 موجودی: {fmt_num(result['balance'])} BP\n"
        f"⭐ +{result['xp_gained']} XP  {bar} Lv.{result['new_level']}"
    )

    if result["leveled_up"]:
        text += f"\n\n🎉 **لول آپ!** به سطح {result['new_level']} رسیدی!"

    await message.reply(text, parse_mode="Markdown")


@router.message(Command("baa"))
async def cmd_baa(message: Message, session: AsyncSession, redis: aioredis.Redis,
                  user: User, group: Group = None, ugs: UserGroupState = None):
    await _process_baa(message, session, redis, user, group, ugs)


@router.message(F.text.regexp(BAA_PATTERN))
async def text_baa(message: Message, session: AsyncSession, redis: aioredis.Redis,
                   user: User = None, group: Group = None, ugs: UserGroupState = None):
    if not user or not group or not ugs:
        return
    await _process_baa(message, session, redis, user, group, ugs)
