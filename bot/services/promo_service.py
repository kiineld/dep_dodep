from sqlalchemy import select, update
from typing import Optional, Tuple

from bot.database import PromoCode, PromoCodeUsage, async_session_maker
from bot.services import user_service


async def validate_promo_code(code: str, user_id: int) -> Tuple[bool, str, Optional[PromoCode]]:
    """Returns (valid, message, promo_code)"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(PromoCode).where(PromoCode.code == code.upper())
        )
        promo = result.scalar_one_or_none()

        if not promo:
            return False, "❌ Промокод не найден", None

        if not promo.is_active:
            return False, "❌ Промокод больше не активен", None

        if promo.used_count >= promo.max_uses:
            return False, "❌ Промокод уже использован максимальное количество раз", None

        # Check if user already used this promo
        usage_result = await session.execute(
            select(PromoCodeUsage).where(
                PromoCodeUsage.promo_code_id == promo.id,
                PromoCodeUsage.user_id == user_id,
            )
        )
        if usage_result.scalar_one_or_none():
            return False, "❌ Вы уже использовали этот промокод", None

        return True, "✅ Промокод действителен", promo


async def apply_promo_code(code: str, user_id: int) -> Tuple[bool, str]:
    """Apply promo code and return (success, message)"""
    valid, msg, promo = await validate_promo_code(code, user_id)
    if not valid:
        return False, msg

    async with async_session_maker() as session:
        # Record usage
        usage = PromoCodeUsage(promo_code_id=promo.id, user_id=user_id)
        session.add(usage)

        # Update used count
        await session.execute(
            update(PromoCode)
            .where(PromoCode.id == promo.id)
            .values(used_count=PromoCode.used_count + 1)
        )
        await session.commit()

    # Apply reward
    if promo.type == "balance":
        new_balance = await user_service.update_user_balance(user_id, promo.value)
        from bot.config import settings
        return True, f"✅ На ваш баланс зачислено {settings.format_price(promo.value)}!"
    elif promo.type == "days":
        return True, f"✅ Промокод активирован! +{promo.value} дней к подписке"
    elif promo.type == "trial":
        return True, f"✅ Пробный период активирован!"
    else:
        return True, "✅ Промокод активирован!"


async def create_promo_code(
    code: str,
    type: str,
    value: int,
    max_uses: int = 1,
) -> PromoCode:
    async with async_session_maker() as session:
        promo = PromoCode(
            code=code.upper(),
            type=type,
            value=value,
            max_uses=max_uses,
        )
        session.add(promo)
        await session.commit()
        await session.refresh(promo)
        return promo


async def get_all_promo_codes():
    async with async_session_maker() as session:
        result = await session.execute(
            select(PromoCode).order_by(PromoCode.created_at.desc())
        )
        return result.scalars().all()


async def deactivate_promo_code(code: str) -> bool:
    async with async_session_maker() as session:
        result = await session.execute(
            select(PromoCode).where(PromoCode.code == code.upper())
        )
        promo = result.scalar_one_or_none()
        if not promo:
            return False
        promo.is_active = False
        await session.commit()
        return True
