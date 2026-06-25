"""
Run once after alembic upgrade head to seed catalog tables.
Usage: python scripts/seed_catalog.py
"""
import asyncio
from bot.models.db import AsyncSessionLocal
from bot.models import SheepCatalog, ToolCatalog, AchievementCatalog


SHEEP = [
    dict(id=1, name="Lamb",         emoji="🐑", cost=50,     base_income_per_min=1,     max_upgrade_level=10, upgrade_cost_base=25,    unlock_level=1,  description="یه بره کوچیک. شروع فروتنانه."),
    dict(id=2, name="Ewe",          emoji="🐏", cost=250,    base_income_per_min=6,     max_upgrade_level=10, upgrade_cost_base=125,   unlock_level=3,  description="یه گوسفند بالغ با درآمد قابل اعتماد."),
    dict(id=3, name="Ram",          emoji="🐐", cost=1000,   base_income_per_min=28,    max_upgrade_level=10, upgrade_cost_base=500,   unlock_level=5,  description="قوی و پربازده."),
    dict(id=4, name="Merino",       emoji="🦙", cost=5000,   base_income_per_min=150,   max_upgrade_level=10, upgrade_cost_base=2500,  unlock_level=8,  description="پشم لوکس، درآمد لوکس."),
    dict(id=5, name="Angora",       emoji="✨", cost=25000,  base_income_per_min=800,   max_upgrade_level=10, upgrade_cost_base=12500, unlock_level=12, description="نرم، پشمالو، و باورنکردنی پرسود."),
    dict(id=6, name="Black Sheep",  emoji="🖤", cost=100000, base_income_per_min=3500,  max_upgrade_level=10, upgrade_cost_base=50000, unlock_level=18, description="نادرترین گوسفند گله."),
    dict(id=7, name="Golden Fleece",emoji="🏆", cost=500000, base_income_per_min=20000, max_upgrade_level=10, upgrade_cost_base=250000,unlock_level=25, description="افسانه‌ای. کمتر کسی دیده."),
]

TOOLS = [
    dict(id=1, name="Bare Hands",   emoji="🤲", cost=0,     max_durability=-1, unlock_level=1,
         yield_table=[{"type":"dried_grass","weight":0.90},{"type":"fresh_hay","weight":0.10}]),
    dict(id=2, name="Sickle",       emoji="🌾", cost=500,   max_durability=30, unlock_level=3,
         yield_table=[{"type":"dried_grass","weight":0.60},{"type":"fresh_hay","weight":0.35},{"type":"alpine_clover","weight":0.05}]),
    dict(id=3, name="Scythe",       emoji="⚔️", cost=2500,  max_durability=25, unlock_level=7,
         yield_table=[{"type":"fresh_hay","weight":0.50},{"type":"alpine_clover","weight":0.40},{"type":"golden_hay","weight":0.10}]),
    dict(id=4, name="Golden Scythe",emoji="🌟", cost=20000, max_durability=20, unlock_level=15,
         yield_table=[{"type":"alpine_clover","weight":0.40},{"type":"golden_hay","weight":0.60}]),
]

ACHIEVEMENTS = [
    dict(id="first_sheep",   name="First Sheep",    emoji="🐑", description="اولین گوسفندت رو بخر",             reward_bp=100),
    dict(id="gatherer",      name="Gatherer",       emoji="🌿", description="۱۰۰ بار جمع‌آوری کن",             reward_bp=500),
    dict(id="investor",      name="Investor",       emoji="📈", description="۱۰,۰۰۰ BP در بانک بذار",          reward_bp=1000),
    dict(id="high_roller",   name="High Roller",    emoji="🎰", description="مجموع ۵۰,۰۰۰ BP قمار کن",        reward_bp=2000),
    dict(id="flock_master",  name="Flock Master",   emoji="👑", description="همزمان ۱۰ گوسفند داشته باش",      reward_bp=3000),
    dict(id="speed_farmer",  name="Speed Farmer",   emoji="⚡", description="۱۰۰ بار پشت هم بع بگو",           reward_bp=500),
    dict(id="legend",        name="Legend",         emoji="🌟", description="به سطح ۲۵ برس",                   reward_bp=10000),
]


async def seed():
    async with AsyncSessionLocal() as session:
        # Sheep catalog
        for data in SHEEP:
            existing = await session.get(SheepCatalog, data["id"])
            if not existing:
                session.add(SheepCatalog(**data))

        # Tool catalog
        for data in TOOLS:
            existing = await session.get(ToolCatalog, data["id"])
            if not existing:
                session.add(ToolCatalog(**data))

        # Achievement catalog
        for data in ACHIEVEMENTS:
            existing = await session.get(AchievementCatalog, data["id"])
            if not existing:
                session.add(AchievementCatalog(**data))

        await session.commit()
        print("✅ Seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
