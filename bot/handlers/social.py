from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import redis.asyncio as aioredis

from bot.models import User, Group, UserGroupState, UserAchievement, AchievementCatalog
from bot.services.level_service import xp_in_current_level
from bot.utils.formatters import fmt_num, xp_bar
from bot.utils.redis_keys import lb_group, lb_global

router = Router()


@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession,
                      user: User, ugs: UserGroupState = None):
    if not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    xp_in_lvl, xp_needed = xp_in_current_level(ugs.xp)
    bar = xp_bar(xp_in_lvl, xp_needed)

    # Count achievements
    ach_result = await session.execute(
        select(UserAchievement).where(UserAchievement.user_id == user.id)
    )
    ach_count = len(ach_result.scalars().all())

    name = user.first_name
    if user.last_name:
        name += f" {user.last_name}"

    await message.reply(
        f"👤 **پروفایل {name}**\n\n"
        f"🎖 سطح: **{ugs.level}**\n"
        f"⭐ XP: {fmt_num(xp_in_lvl)} / {fmt_num(xp_needed)}\n"
        f"{bar}\n\n"
        f"💰 Baa Points: **{fmt_num(ugs.baa_points)}**\n"
        f"🏦 بانک: {fmt_num(ugs.bank_balance)} BP\n"
        f"🐑 تعداد بع: {fmt_num(ugs.total_baa_count)}\n"
        f"📈 کل کسب‌شده: {fmt_num(ugs.total_earned)} BP\n"
        f"🏆 دستاوردها: {ach_count}\n"
        f"🔥 استریک روزانه: {ugs.daily_streak} روز",
        parse_mode="Markdown"
    )


@router.message(Command("leaderboard", "lb"))
async def cmd_leaderboard(message: Message, session: AsyncSession, redis: aioredis.Redis,
                          group: Group = None):
    if not group:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    result = await session.execute(
        select(UserGroupState, User)
        .join(User, UserGroupState.user_id == User.id)
        .where(UserGroupState.group_id == group.id)
        .order_by(desc(UserGroupState.baa_points))
        .limit(10)
    )
    rows = result.all()

    if not rows:
        return await message.reply("هنوز کسی امتیاز نداره!")

    medals = ["🥇", "🥈", "🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = [f"🏆 **لیدربورد گروه**\n"]
    for i, (ugs, u) in enumerate(rows):
        name = u.first_name[:15]
        lines.append(f"{medals[i]} {name} — {fmt_num(ugs.baa_points)} BP (Lv.{ugs.level})")

    await message.reply("\n".join(lines), parse_mode="Markdown")


@router.message(Command("globalboard"))
async def cmd_globalboard(message: Message, session: AsyncSession):
    result = await session.execute(
        select(UserGroupState, User)
        .join(User, UserGroupState.user_id == User.id)
        .order_by(desc(UserGroupState.baa_points))
        .limit(10)
    )
    rows = result.all()

    medals = ["🥇", "🥈", "🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = [f"🌍 **لیدربورد جهانی**\n"]
    for i, (ugs, u) in enumerate(rows):
        name = u.first_name[:15]
        lines.append(f"{medals[i]} {name} — {fmt_num(ugs.baa_points)} BP (Lv.{ugs.level})")

    await message.reply("\n".join(lines), parse_mode="Markdown")


@router.message(Command("achievements"))
async def cmd_achievements(message: Message, session: AsyncSession, user: User):
    result = await session.execute(
        select(UserAchievement, AchievementCatalog)
        .join(AchievementCatalog, UserAchievement.achievement_id == AchievementCatalog.id)
        .where(UserAchievement.user_id == user.id)
        .order_by(UserAchievement.unlocked_at)
    )
    rows = result.all()

    if not rows:
        return await message.reply("🏅 هنوز دستاوردی نداری. بازی کن تا باز بشن!")

    lines = ["🏆 **دستاوردهای تو**\n"]
    for ua, ac in rows:
        lines.append(f"{ac.emoji} **{ac.name}** — {ac.description}")

    await message.reply("\n".join(lines), parse_mode="Markdown")
