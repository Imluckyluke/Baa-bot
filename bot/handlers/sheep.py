from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from bot.models import User, Group, UserGroupState
from bot.services.sheep_service import SheepService
from bot.utils.formatters import fmt_num, hunger_emoji, FOOD_NAMES

router = Router()


@router.message(Command("shop"))
async def cmd_shop(message: Message, session: AsyncSession, redis: aioredis.Redis,
                   ugs: UserGroupState = None):
    if not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    service = SheepService(session, redis)
    catalog = await service.get_catalog()

    lines = ["🏪 **فروشگاه گوسفند**\n"]
    for item in catalog:
        lock = "🔒 " if ugs.level < item.unlock_level else ""
        lines.append(
            f"{lock}{item.emoji} **{item.name}** (شناسه: {item.id})\n"
            f"   💰 {fmt_num(item.cost)} BP | 📈 {item.base_income_per_min}/دقیقه\n"
            f"   🔓 لول {item.unlock_level} | {item.description}\n"
        )
    lines.append("\nبرای خرید: `/buy sheep <شناسه>`")
    await message.reply("\n".join(lines), parse_mode="Markdown")


@router.message(Command("buy"))
async def cmd_buy(message: Message, session: AsyncSession, redis: aioredis.Redis,
                  user: User, group: Group = None, ugs: UserGroupState = None):
    if not group or not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    args = (message.text or "").split()
    if len(args) < 3 or args[1].lower() != "sheep":
        return await message.reply("استفاده: `/buy sheep <شناسه>`", parse_mode="Markdown")

    try:
        catalog_id = int(args[2])
    except ValueError:
        return await message.reply("شناسه باید عدد باشه.")

    service = SheepService(session, redis)
    try:
        sheep = await service.buy_sheep(user.id, group.id, catalog_id, ugs)
        cat = sheep.catalog
        await message.reply(
            f"✅ {cat.emoji} **{cat.name}** خریداری شد!\n"
            f"📈 درآمد پایه: {cat.base_income_per_min} BP/دقیقه\n"
            f"🔑 شناسه: `{sheep.id}`",
            parse_mode="Markdown"
        )
    except ValueError as e:
        err = str(e)
        if err.startswith("NO_BALANCE:"):
            bal = err.split(":")[1]
            await message.reply(f"💸 Baa Point کافی نداری. موجودی: {fmt_num(int(bal))} BP")
        elif err.startswith("LEVEL_REQUIRED:"):
            lvl = err.split(":")[1]
            await message.reply(f"🔒 این گوسفند در سطح {lvl} باز می‌شه. سطح فعلی تو: {ugs.level}")
        else:
            await message.reply(f"❌ {err}")


@router.message(Command("mysheep"))
async def cmd_mysheep(message: Message, session: AsyncSession, redis: aioredis.Redis,
                      user: User, group: Group = None, ugs: UserGroupState = None):
    if not group:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    service = SheepService(session, redis)
    sheep_list = await service.get_user_sheep(user.id, group.id)

    if not sheep_list:
        return await message.reply(
            "🐑 هنوز گوسفندی نداری!\n"
            "از /shop برای خرید استفاده کن."
        )

    total_pending = sum(s.pending_income for s in sheep_list)
    lines = [f"🐑 **گوسفندهای تو** ({len(sheep_list)} عدد)\n"]

    for s in sheep_list:
        h = float(s.hunger_pct)
        income = service.income_per_min(s)
        name = s.nickname or s.catalog.name
        lines.append(
            f"{s.catalog.emoji} **{name}** (Lv.{s.upgrade_level})\n"
            f"   {hunger_emoji(h)} گرسنگی: {h:.0f}% | 📈 {income:.1f} BP/دقیقه\n"
            f"   💰 معلق: {fmt_num(s.pending_income)} BP | 🔑 `{str(s.id)[:8]}...`\n"
        )

    lines.append(f"\n💰 کل معلق: {fmt_num(total_pending)} BP")
    lines.append("برای دریافت: /collect")
    await message.reply("\n".join(lines), parse_mode="Markdown")


@router.message(Command("collect"))
async def cmd_collect(message: Message, session: AsyncSession, redis: aioredis.Redis,
                      user: User, group: Group = None):
    if not group:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    service = SheepService(session, redis)
    total = await service.collect_all(user.id, group.id)

    if total == 0:
        await message.reply("🌾 هنوز درآمدی جمع نشده. کمی صبر کن!")
    else:
        await message.reply(f"✅ **{fmt_num(total)} Baa Point** جمع‌آوری شد! 🐑💰", parse_mode="Markdown")


@router.message(Command("upgrade"))
async def cmd_upgrade(message: Message, session: AsyncSession, redis: aioredis.Redis,
                      user: User, group: Group = None, ugs: UserGroupState = None):
    if not group or not ugs:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    args = (message.text or "").split()
    if len(args) < 2:
        return await message.reply("استفاده: `/upgrade <شناسه_گوسفند>`", parse_mode="Markdown")

    sheep_id_prefix = args[1]
    service = SheepService(session, redis)
    sheep_list = await service.get_user_sheep(user.id, group.id)

    # Match by prefix
    matched = [s for s in sheep_list if str(s.id).startswith(sheep_id_prefix)]
    if not matched:
        return await message.reply("❌ گوسفند پیدا نشد. از /mysheep شناسه رو کپی کن.")
    if len(matched) > 1:
        return await message.reply("❌ شناسه مبهمه. بیشتر کاراکتر وارد کن.")

    sheep = matched[0]
    cost = service.upgrade_cost(sheep.catalog, sheep.upgrade_level)

    try:
        sheep = await service.upgrade_sheep(sheep, user.id, group.id, ugs)
        await message.reply(
            f"⬆️ **{sheep.catalog.emoji} {sheep.catalog.name}** ارتقا یافت!\n"
            f"سطح: {sheep.upgrade_level} | هزینه: {fmt_num(cost)} BP\n"
            f"📈 درآمد جدید: {service.income_per_min(sheep):.1f} BP/دقیقه",
            parse_mode="Markdown"
        )
    except ValueError as e:
        err = str(e)
        if "NO_BALANCE" in err:
            await message.reply(f"💸 BP کافی نداری. هزینه ارتقا: {fmt_num(cost)} BP")
        else:
            await message.reply(f"❌ {err}")


@router.message(Command("feed"))
async def cmd_feed(message: Message, session: AsyncSession, redis: aioredis.Redis,
                   user: User, group: Group = None):
    if not group:
        return await message.reply("این دستور فقط در گروه کار می‌کنه.")

    args = (message.text or "").split()
    if len(args) < 3:
        return await message.reply(
            "استفاده: `/feed <شناسه_گوسفند> <نوع_غذا>`\n"
            "نوع‌ها: `dried_grass` | `fresh_hay` | `alpine_clover` | `golden_hay`",
            parse_mode="Markdown"
        )

    sheep_id_prefix = args[1]
    food_type = args[2].lower()

    service = SheepService(session, redis)
    sheep_list = await service.get_user_sheep(user.id, group.id)
    matched = [s for s in sheep_list if str(s.id).startswith(sheep_id_prefix)]

    if not matched:
        return await message.reply("❌ گوسفند پیدا نشد.")

    sheep = matched[0]
    try:
        result = await service.feed_sheep(sheep, user.id, group.id, food_type)
        food_name = FOOD_NAMES.get(food_type, food_type)
        await message.reply(
            f"🌾 {sheep.catalog.emoji} **{sheep.nickname or sheep.catalog.name}** تغذیه شد!\n"
            f"غذا: {food_name}\n"
            f"گرسنگی: {result['new_hunger']:.0f}%",
            parse_mode="Markdown"
        )
    except ValueError as e:
        if "NO_FOOD" in str(e):
            await message.reply(f"❌ {FOOD_NAMES.get(food_type, food_type)} در انبار نداری. از /gather استفاده کن.")
        else:
            await message.reply(f"❌ {e}")
