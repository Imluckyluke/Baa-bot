from sqlalchemy.ext.asyncio import AsyncSession
from bot.models import UserGroupState


def xp_for_level(level: int) -> int:
    """XP required to reach `level` from level-1."""
    return level * level * 100


def total_xp_for_level(level: int) -> int:
    return sum(xp_for_level(l) for l in range(2, level + 1))


def level_from_xp(xp: int) -> int:
    level = 1
    while True:
        needed = xp_for_level(level + 1)
        if xp < needed:
            return level
        xp -= needed
        level += 1


def xp_in_current_level(xp: int) -> tuple[int, int]:
    """Returns (xp_in_level, xp_needed_for_next_level)."""
    level = 1
    while True:
        needed = xp_for_level(level + 1)
        if xp < needed:
            return xp, needed
        xp -= needed
        level += 1


class LevelService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def award_xp(self, state: UserGroupState, xp: int) -> tuple[bool, int]:
        """
        Awards XP and checks for level up.
        Returns (leveled_up, new_level).
        """
        old_level = state.level
        state.xp += xp
        new_level = level_from_xp(state.xp)

        if new_level > old_level:
            state.level = new_level
            await self.session.commit()
            return True, new_level

        await self.session.commit()
        return False, old_level

    def xp_progress(self, state: UserGroupState) -> tuple[int, int, int]:
        """Returns (current_level_xp, next_level_xp_needed, level)."""
        xp_in_lvl, xp_needed = xp_in_current_level(state.xp)
        return xp_in_lvl, xp_needed, state.level
