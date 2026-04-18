from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, Text, func
from datetime import datetime
from typing import Optional
import os

from bot.config import settings

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram ID
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)  # kopecks
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False)
    remnawave_uuid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    referrer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    remnawave_uuid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    vpn_type: Mapped[str] = mapped_column(String(32))  # basic | whitelist
    devices: Mapped[int] = mapped_column(Integer, default=1)
    traffic_gb: Mapped[int] = mapped_column(Integer, default=500)
    days: Mapped[int] = mapped_column(Integer)
    price_kopecks: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | expired | pending
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    amount_kopecks: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32))  # topup | purchase | bonus | refund
    description: Mapped[str] = mapped_column(String(256), default="")
    payment_provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    payment_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | completed | failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    type: Mapped[str] = mapped_column(String(32))  # balance | days | trial
    value: Mapped[int] = mapped_column(Integer)  # kopecks or days
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class PromoCodeUsage(Base):
    __tablename__ = "promo_code_usages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promo_code_id: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(BigInteger)
    used_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    message_text: Mapped[str] = mapped_column(Text)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
