from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional, List

from bot.database import Subscription, Transaction, async_session_maker


async def create_subscription(
    user_id: int,
    vpn_type: str,
    devices: int,
    traffic_gb: int,
    days: int,
    price_kopecks: int,
    remnawave_uuid: Optional[str] = None,
) -> Subscription:
    async with async_session_maker() as session:
        sub = Subscription(
            user_id=user_id,
            remnawave_uuid=remnawave_uuid,
            vpn_type=vpn_type,
            devices=devices,
            traffic_gb=traffic_gb,
            days=days,
            price_kopecks=price_kopecks,
            status="active",
            expires_at=datetime.utcnow() + timedelta(days=days),
        )
        session.add(sub)
        await session.commit()
        await session.refresh(sub)
        return sub


async def get_user_subscriptions(user_id: int) -> List[Subscription]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
        )
        return result.scalars().all()


async def get_active_subscription(user_id: int) -> Optional[Subscription]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
                Subscription.expires_at > datetime.utcnow(),
            )
            .order_by(Subscription.expires_at.desc())
        )
        return result.scalars().first()


async def create_transaction(
    user_id: int,
    amount_kopecks: int,
    type: str,
    description: str = "",
    payment_provider: Optional[str] = None,
    payment_id: Optional[str] = None,
    status: str = "pending",
) -> Transaction:
    async with async_session_maker() as session:
        tx = Transaction(
            user_id=user_id,
            amount_kopecks=amount_kopecks,
            type=type,
            description=description,
            payment_provider=payment_provider,
            payment_id=payment_id,
            status=status,
        )
        session.add(tx)
        await session.commit()
        await session.refresh(tx)
        return tx


async def complete_transaction(tx_id: int) -> Optional[Transaction]:
    async with async_session_maker() as session:
        result = await session.execute(select(Transaction).where(Transaction.id == tx_id))
        tx = result.scalar_one_or_none()
        if tx:
            tx.status = "completed"
            await session.commit()
        return tx


async def get_user_transactions(user_id: int, limit: int = 10) -> List[Transaction]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


async def get_total_revenue() -> int:
    """Returns total completed revenue in kopecks"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(func.sum(Transaction.amount_kopecks))
            .where(
                Transaction.status == "completed",
                Transaction.type.in_(["topup", "purchase"]),
            )
        )
        return result.scalar_one() or 0


async def get_subscriptions_count() -> int:
    async with async_session_maker() as session:
        result = await session.execute(
            select(func.count(Subscription.id)).where(Subscription.status == "active")
        )
        return result.scalar_one()
