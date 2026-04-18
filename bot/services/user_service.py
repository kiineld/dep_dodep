from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from bot.database import User, async_session_maker


async def get_or_create_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    referrer_id: Optional[int] = None,
) -> User:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.id == telegram_id))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                referrer_id=referrer_id,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            # Update info
            changed = False
            if username and user.username != username:
                user.username = username
                changed = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                changed = True
            if changed:
                await session.commit()
                await session.refresh(user)

        return user


async def get_user(telegram_id: int) -> Optional[User]:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.id == telegram_id))
        return result.scalar_one_or_none()


async def update_user_balance(telegram_id: int, amount_kopecks: int) -> int:
    """Add amount_kopecks to balance (can be negative). Returns new balance."""
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError(f"User {telegram_id} not found")
        user.balance += amount_kopecks
        await session.commit()
        return user.balance


async def set_user_remnawave_uuid(telegram_id: int, uuid: str):
    async with async_session_maker() as session:
        await session.execute(
            update(User).where(User.id == telegram_id).values(remnawave_uuid=uuid)
        )
        await session.commit()


async def set_trial_used(telegram_id: int):
    async with async_session_maker() as session:
        await session.execute(
            update(User).where(User.id == telegram_id).values(trial_used=True)
        )
        await session.commit()


async def ban_user(telegram_id: int):
    async with async_session_maker() as session:
        await session.execute(
            update(User).where(User.id == telegram_id).values(is_banned=True)
        )
        await session.commit()


async def unban_user(telegram_id: int):
    async with async_session_maker() as session:
        await session.execute(
            update(User).where(User.id == telegram_id).values(is_banned=False)
        )
        await session.commit()


async def get_all_users_count() -> int:
    from sqlalchemy import func as sqlfunc
    async with async_session_maker() as session:
        result = await session.execute(select(sqlfunc.count(User.id)))
        return result.scalar_one()


async def get_all_user_ids() -> list:
    async with async_session_maker() as session:
        result = await session.execute(select(User.id).where(User.is_banned == False))
        return [row[0] for row in result.all()]
