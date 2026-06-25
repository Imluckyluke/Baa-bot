def fmt_num(n: int | float) -> str:
    """Format large numbers with K/M suffix."""
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def xp_bar(current_xp: int, next_xp: int, width: int = 10) -> str:
    """Unicode XP progress bar."""
    ratio = min(current_xp / next_xp, 1.0) if next_xp > 0 else 1.0
    filled = int(ratio * width)
    return "█" * filled + "░" * (width - filled)


def fmt_time(seconds: int) -> str:
    """Format seconds into human-readable countdown."""
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def hunger_emoji(hunger_pct: float) -> str:
    if hunger_pct < 25:
        return "🟢"
    if hunger_pct < 50:
        return "🟡"
    if hunger_pct < 75:
        return "🟠"
    if hunger_pct < 100:
        return "🔴"
    return "💀"


FOOD_NAMES = {
    "dried_grass": "🌱 علف خشک",
    "fresh_hay": "🌾 یونجه تازه",
    "alpine_clover": "🍀 شبدر کوهی",
    "golden_hay": "✨ علف طلایی",
}

FOOD_HUNGER_RESTORE = {
    "dried_grass": 15,
    "fresh_hay": 35,
    "alpine_clover": 60,
    "golden_hay": 100,
}
