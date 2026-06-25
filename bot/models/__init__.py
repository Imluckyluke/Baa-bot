from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
import uuid


class Base(DeclarativeBase):
    pass


class Group(Base):
    __tablename__ = "groups"

    id = Column(BigInteger, primary_key=True)
    title = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    baa_cooldown_sec = Column(Integer, default=300, nullable=False)
    baa_base_reward = Column(Integer, default=40, nullable=False)
    baa_xp_reward = Column(Integer, default=10, nullable=False)
    gathering_cooldown_sec = Column(Integer, default=600, nullable=False)
    bank_interest_rate = Column(Numeric(5, 4), default=0.02, nullable=False)
    casino_enabled = Column(Boolean, default=True, nullable=False)
    minigames_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    username = Column(Text, nullable=True)
    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=True)
    is_banned = Column(Boolean, default=False, nullable=False)
    ban_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserGroupState(Base):
    __tablename__ = "user_group_state"
    __table_args__ = (UniqueConstraint("user_id", "group_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(BigInteger, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)

    baa_points = Column(BigInteger, default=0, nullable=False)
    bank_balance = Column(BigInteger, default=0, nullable=False)
    bank_deposited_at = Column(DateTime(timezone=True), nullable=True)

    xp = Column(BigInteger, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)

    last_baa_at = Column(DateTime(timezone=True), nullable=True)
    last_gather_at = Column(DateTime(timezone=True), nullable=True)
    last_daily_at = Column(DateTime(timezone=True), nullable=True)
    daily_streak = Column(Integer, default=0, nullable=False)

    casino_daily_spent = Column(BigInteger, default=0, nullable=False)
    casino_date = Column(Date, nullable=True)

    total_baa_count = Column(BigInteger, default=0, nullable=False)
    total_earned = Column(BigInteger, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SheepCatalog(Base):
    __tablename__ = "sheep_catalog"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    emoji = Column(Text, nullable=False)
    cost = Column(BigInteger, nullable=False)
    base_income_per_min = Column(Numeric(12, 4), nullable=False)
    max_upgrade_level = Column(Integer, default=10, nullable=False)
    upgrade_cost_base = Column(BigInteger, nullable=False)
    unlock_level = Column(Integer, default=1, nullable=False)
    description = Column(Text, nullable=True)


class OwnedSheep(Base):
    __tablename__ = "owned_sheep"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    group_id = Column(BigInteger, ForeignKey("groups.id"), nullable=False)
    catalog_id = Column(Integer, ForeignKey("sheep_catalog.id"), nullable=False)

    nickname = Column(Text, nullable=True)
    upgrade_level = Column(Integer, default=0, nullable=False)
    hunger_pct = Column(Numeric(5, 2), default=0.0, nullable=False)
    last_hunger_tick = Column(DateTime(timezone=True), server_default=func.now())
    last_income_tick = Column(DateTime(timezone=True), server_default=func.now())
    pending_income = Column(BigInteger, default=0, nullable=False)
    is_alive = Column(Boolean, default=True, nullable=False)
    purchased_at = Column(DateTime(timezone=True), server_default=func.now())

    catalog = relationship("SheepCatalog", lazy="joined")


class ToolCatalog(Base):
    __tablename__ = "tool_catalog"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    emoji = Column(Text, nullable=False)
    cost = Column(BigInteger, nullable=False)
    max_durability = Column(Integer, nullable=False)
    unlock_level = Column(Integer, default=1, nullable=False)
    yield_table = Column(JSONB, nullable=False)


class OwnedTool(Base):
    __tablename__ = "owned_tools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    group_id = Column(BigInteger, ForeignKey("groups.id"), nullable=False)
    catalog_id = Column(Integer, ForeignKey("tool_catalog.id"), nullable=False)
    durability_remaining = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    purchased_at = Column(DateTime(timezone=True), server_default=func.now())

    catalog = relationship("ToolCatalog", lazy="joined")


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("user_id", "group_id", "item_type"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    group_id = Column(BigInteger, ForeignKey("groups.id"), nullable=False)
    item_type = Column(Text, nullable=False)
    quantity = Column(Integer, default=0, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    group_id = Column(BigInteger, ForeignKey("groups.id"), nullable=False)
    type = Column(Text, nullable=False)
    amount = Column(BigInteger, nullable=False)
    balance_after = Column(BigInteger, nullable=False)
    meta = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AchievementCatalog(Base):
    __tablename__ = "achievement_catalog"

    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    emoji = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    reward_bp = Column(Integer, default=0, nullable=False)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    user_id = Column(BigInteger, ForeignKey("users.id"), primary_key=True)
    achievement_id = Column(Text, ForeignKey("achievement_catalog.id"), primary_key=True)
    unlocked_at = Column(DateTime(timezone=True), server_default=func.now())


class CasinoLog(Base):
    __tablename__ = "casino_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    group_id = Column(BigInteger, ForeignKey("groups.id"), nullable=False)
    game = Column(Text, nullable=False)
    bet_amount = Column(BigInteger, nullable=False)
    payout = Column(BigInteger, nullable=False)
    net = Column(BigInteger, nullable=False)
    meta = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MinigameSession(Base):
    __tablename__ = "minigame_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(BigInteger, ForeignKey("groups.id"), nullable=False)
    game_type = Column(Text, nullable=False)
    initiator_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    opponent_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    pot = Column(BigInteger, default=0, nullable=False)
    state = Column(Text, default="waiting", nullable=False)
    result = Column(JSONB, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
