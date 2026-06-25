from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import redis.asyncio as aioredis

from bot.models import User, Group, UserGroupState, UserGroupState
from bot.config import settings
from bot.utils.formatters import fmt_num
from bot.utils.redis_keys import maintenance

router = Router()


async def _is_admin(message: Message, session: AsyncSession) -> bool:
    """Check if user is Telegram group admin or bot operator."""
    if message.from_user.id in settings.OPERATOR_IDS:
        return True
    if message.chat.type in ("group", "supergroup"):
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ("administrator", "creator")
    return False


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, redis: aioredis.Redis,
                    group: Group = None):
    if not await _is_admin(message, session):
        return await message.reply("🚫 فقط ادمین‌های گروه می‌تونن از این دستور استفاده کنن.")

    args = (message.text or "").split()
    if len(args) < 2:
        return await message.reply(
            "⚙️ **دستورات ادمین**\n\n"
            "`/admin stats` — آمار گروه\n"
            "`/admin setcooldown <ثانیه>` — کول‌داون بع\n"
            "`/admin setreward <مقدار>` — جایزه بع\n"
            "`/admin setinterest <نرخ>` — نرخ سود بانک\n"
            "`/admin toggle casino` — کازینو on/off\n"
            "`/admin toggle minigames` — مینی‌گیم‌ها on/off\n"
            "`/admin ban @user` — مسدود کردن\n"
            "`/admin unban @user` — رفع مسدود",
            parse_mode="Markdown"
        )

    sub = args[1].lower()

    if sub == "stats":
        if not group:
            return await message.reply("در گروه استفاده کن.")
        count_result = await session.execute(
            select(func.count()).where(UserGroupState.group_id == group.id)
        )
        user_count = count_result.scalar()
        total_bp_result = await session.execute(
            select(func.sum(UserGroupState.baa_points)).where(UserGroupState.group_id == group.id)
        )
        total_bp = total_bp_result.scalar() or 0
        await message.reply(
            f"📊 **آمار گروه {group.title}**\n\n"
            f"👥 کاربران: {user_count}\n"
            f"💰 کل BP در گردش: {fmt_num(total_bp)}\n"
            f"⏱ کول‌داون: {group.baa_cooldown_sec}s\n"
            f"🎁 جایزه بع: {group.baa_base_reward} BP\n"
            f"🏦 نرخ بانک: {float(group.bank_interest_rate)*100:.1f}%/h\n"
            f"🎰 کازینو: {'✅' if group.casino_enabled else '❌'}\n"
            f"🎮 مینی‌گیم‌ها: {'✅' if group.minigames_enabled else '❌'}",
            parse_mode="Markdown"
        )

    elif sub == "setcooldown" and len(args) >= 3:
        if not group:
            return
        try:
            val = int(args[2])
            if val < 30:
                raise ValueError
            group.baa_cooldown_sec = val
            await session.commit()
            await message.reply(f"✅ کول‌داون بع به {val} ثانیه تنظیم شد.")
        except ValueError:
            await message.reply("❌ حداقل ۳۰ ثانیه.")

    elif sub == "setreward" and len(args) >= 3:
        if not group:
            return
        try:
            val = int(args[2])
            group.baa_base_reward = val
            await session.commit()
            await message.reply(f"✅ جایزه بع به {val} BP تنظیم شد.")
        except ValueError:
            await message.reply("❌ مقدار نامعتبر.")

    elif sub == "setinterest" and len(args) >= 3:
        if not group:
            return
        try:
            val = float(args[2])
            if not 0 <= val <= 0.5:
                raise ValueError
            group.bank_interest_rate = val
            await session.commit()
            await message.reply(f"✅ نرخ سود به {val*100:.1f}%/ساعت تنظیم شد.")
        except ValueError:
            await message.reply("❌ نرخ باید بین ۰ و ۰.۵ باشه.")

    elif sub == "toggle" and len(args) >= 3:
        if not group:
            return
        feature = args[2].lower()
        if feature == "casino":
            group.casino_enabled = not group.casino_enabled
            await session.commit()
            state = "✅ فعال" if group.casino_enabled else "❌ غیرفعال"
            await message.reply(f"🎰 کازینو: {state}")
        elif feature == "minigames":
            group.minigames_enabled = not group.minigames_enabled
            await session.commit()
            state = "✅ فعال" if group.minigames_enabled else "❌ غیرفعال"
            await message.reply(f"🎮 مینی‌گیم‌ها: {state}")
        else:
            await message.reply("❌ ویژگی ناشناخته.")

    elif sub == "ban" and len(args) >= 3:
        mention = args[2].lstrip("@")
        result = await session.execute(select(User).where(User.username == mention))
        target = result.scalar_one_or_none()
        if not target:
            return await message.reply("❌ کاربر پیدا نشد.")
        reason = " ".join(args[3:]) if len(args) > 3 else "توسط ادمین"
        target.is_banned = True
        target.ban_reason = reason
        await session.commit()
        await message.reply(f"🚫 @{mention} مسدود شد.")

    elif sub == "unban" and len(args) >= 3:
        mention = args[2].lstrip("@")
        result = await session.execute(select(User).where(User.username == mention))
        target = result.scalar_one_or_none()
        if not target:
            return await message.reply("❌ کاربر پیدا نشد.")
        target.is_banned = False
        target.ban_reason = None
        await session.commit()
        await message.reply(f"✅ @{mention} رفع مسدود شد.")

    else:
        await message.reply("❌ دستور ناشناخته. `/admin` برای راهنما.", parse_mode="Markdown")


# ── OPERATOR ──────────────────────────────────────────────────────────────────
@router.message(Command("op"))
async def cmd_op(message: Message, session: AsyncSession, redis: aioredis.Redis):
    if message.from_user.id not in settings.OPERATOR_IDS:
        return

    args = (message.text or "").split()
    if len(args) < 2:
        return

    sub = args[1].lower()
    if sub == "maintenance":
        mode = args[2].lower() if len(args) >= 3 else "on"
        if mode == "on":
            await redis.set(maintenance(), 1)
            await message.reply("🔧 حالت تعمیر فعال شد.")
        else:
            await redis.delete(maintenance())
            await message.reply("✅ ربات برگشت.")
