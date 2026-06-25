from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    OPERATOR_IDS: List[int] = []

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://baabot:baabot@localhost:5432/baabot"
    DB_POOL_SIZE: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Game defaults
    DEFAULT_BAA_COOLDOWN: int = 300
    DEFAULT_BAA_REWARD: int = 40
    DEFAULT_BAA_XP: int = 10
    DEFAULT_GATHER_COOLDOWN: int = 600
    DEFAULT_BANK_INTEREST_RATE: float = 0.02
    DEFAULT_CASINO_DAILY_LIMIT: int = 50000
    HUNGER_GAIN_RATE_PER_HOUR: float = 10.0
    INCOME_TICK_MINUTES: int = 1
    HUNGER_TICK_MINUTES: int = 5
    CASINO_MIN_BET: int = 10
    CASINO_MAX_BET: int = 100000

    # Misc
    LOG_LEVEL: str = "INFO"
    MAINTENANCE: bool = False

    @field_validator("OPERATOR_IDS", mode="before")
    @classmethod
    def parse_operator_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_postgres_url(cls, v):
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and "+asyncpg" not in v:
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
