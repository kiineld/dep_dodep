from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.config import settings
from bot.database import User
from bot.keyboards.user import (
    vpn_category_keyboard,
    devices_keyboard,
    period_keyboard,
    payment_method_keyboard,
    payment_link_keyboard,
    cancel_keyboard,
    main_menu_keyboard,
)
from bot.services.remnawave import remnawave
from bot.services.subscription_service import create_subscription, create_transaction, complete_transaction
from bot.services.user_service import update_user_balance, set_user_remnawave_uuid
from bot.states import BuyFlow
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = Router()


async def _edit_or_send(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_caption(
            caption=text, reply_markup=reply_markup, parse_mode="HTML"
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text=text, reply_markup=reply_markup, parse_mode="HTML"
            )
        except Exception:
            await callback.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


# ── Step 1: Choose VPN category ──────────────────────────────────────────────

@router.callback_query(F.data == "buy_subscription")
async def cb_buy_start(callback: CallbackQuery, db_user: User, state: FSMContext):
    await state.clear()
    if db_user.is_banned:
        await callback.answer("🚫 Вы заблокированы", show_alert=True)
        return

    count = await remnawave.get_active_nodes_count()
    text = (
        "🌐 <b>Выберите категорию VPN</b>\n\n"
        f"Доступных серверов — <b>{count}</b>"
    )
    await _edit_or_send(callback, text, vpn_category_keyboard(count))
    await state.set_state(BuyFlow.choosing_category)
    await callback.answer()


# ── Step 2: Choose devices ────────────────────────────────────────────────────

@router.callback_query(BuyFlow.choosing_category, F.data.startswith("vpn_type:"))
async def cb_vpn_type(callback: CallbackQuery, db_user: User, state: FSMContext):
    vpn_type = callback.data.split(":")[1]  # basic | whitelist
    await state.update_data(vpn_type=vpn_type)

    count = await remnawave.get_active_nodes_count()
    type_name = "Базовый VPN" if vpn_type == "basic" else "Белые списки VPN"
    text = (
        f"📱 <b>Выберите максимальное количество устройств, на которых планируете пользоваться нашим сервисом</b>\n\n"
        f"Тариф: <b>{type_name}</b>\n"
        f"Доступных серверов — <b>{count}</b>"
    )
    await _edit_or_send(callback, text, devices_keyboard())
    await state.set_state(BuyFlow.choosing_devices)
    await callback.answer()


# ── Step 3: Choose period ─────────────────────────────────────────────────────

@router.callback_query(BuyFlow.choosing_devices, F.data.startswith("devices:"))
async def cb_devices(callback: CallbackQuery, db_user: User, state: FSMContext):
    _, devices_str, traffic_str = callback.data.split(":")
    devices = int(devices_str)
    traffic_gb = int(traffic_str)
    await state.update_data(devices=devices, traffic_gb=traffic_gb)

    data = await state.get_data()
    vpn_type = data.get("vpn_type", "basic")
    premium = vpn_type == "whitelist"

    text = (
        "📅 <b>Выберите как часто вы планируете оплачивать наш сервис</b>\n\n"
        f"Доступных серверов — <b>{await remnawave.get_active_nodes_count()}</b>"
    )
    await _edit_or_send(callback, text, period_keyboard(vpn_type))
    await state.set_state(BuyFlow.choosing_period)
    await callback.answer()


# ── Step 4: Choose payment method ────────────────────────────────────────────

@router.callback_query(BuyFlow.choosing_period, F.data.startswith("period:"))
async def cb_period(callback: CallbackQuery, db_user: User, state: FSMContext):
    days = int(callback.data.split(":")[1])
    data = await state.get_data()
    vpn_type = data.get("vpn_type", "basic")
    premium = vpn_type == "whitelist"
    price_kopecks = settings.get_plan_price(days, premium)

    await state.update_data(days=days, price_kopecks=price_kopecks)

    text = (
        "💳 <b>Перейдите по ссылке для оплаты</b>\n\n"
        f"Тариф: <b>{'Белые списки VPN' if premium else 'Базовый VPN'}</b>\n"
        f"Период: <b>{days} дней</b>\n"
        f"Устройств: <b>{data.get('devices', 5)}</b>\n"
        f"Трафик: <b>{data.get('traffic_gb', 500)} GB</b>\n"
        f"Стоимость: <b>{settings.format_price(price_kopecks)}</b>\n\n"
        f"💼 Ваш баланс: <b>{settings.format_price(db_user.balance)}</b>"
    )

    kb = payment_method_keyboard(
        yookassa=settings.yookassa_enabled,
        cryptobot=settings.cryptobot_enabled,
        stars=settings.telegram_stars_enabled,
    )
    await _edit_or_send(callback, text, kb)
    await state.set_state(BuyFlow.choosing_payment)
    await callback.answer()


# ── Pay with balance ──────────────────────────────────────────────────────────

@router.callback_query(BuyFlow.choosing_payment, F.data == "pay:balance")
async def cb_pay_balance(callback: CallbackQuery, db_user: User, state: FSMContext):
    data = await state.get_data()
    price_kopecks = data.get("price_kopecks", 0)

    if db_user.balance < price_kopecks:
        shortage = price_kopecks - db_user.balance
        text = (
            f"❌ <b>Недостаточно средств на балансе</b>\n\n"
            f"Необходимо: <b>{settings.format_price(price_kopecks)}</b>\n"
            f"На балансе: <b>{settings.format_price(db_user.balance)}</b>\n"
            f"Не хватает: <b>{settings.format_price(shortage)}</b>\n\n"
            "Пополните баланс и попробуйте снова."
        )
        from bot.keyboards.user import back_button
        await _edit_or_send(callback, text, back_button("buy_subscription"))
        await callback.answer()
        return

    # Deduct balance and create subscription
    await _purchase_subscription(callback, db_user, state, payment_provider="balance")


async def _purchase_subscription(
    callback: CallbackQuery,
    db_user: User,
    state: FSMContext,
    payment_provider: str,
    payment_id: str = None,
):
    data = await state.get_data()
    vpn_type = data.get("vpn_type", "basic")
    devices = data.get("devices", 5)
    traffic_gb = data.get("traffic_gb", 500)
    days = data.get("days", 30)
    price_kopecks = data.get("price_kopecks", 0)

    # Deduct balance
    if payment_provider == "balance":
        new_balance = await update_user_balance(db_user.id, -price_kopecks)

    # Create/update in Remnawave
    remnawave_uuid = db_user.remnawave_uuid
    traffic_bytes = traffic_gb * 1024 * 1024 * 1024
    expire_at = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    if not remnawave_uuid:
        username = db_user.username or f"user_{db_user.id}"
        rw_user = await remnawave.create_user(
            telegram_id=db_user.id,
            username=username,
            traffic_limit_bytes=traffic_bytes,
            expire_at=expire_at,
            description=f"Bot purchase: {vpn_type} {days}d",
        )
        if rw_user:
            remnawave_uuid = rw_user.get("uuid")
            if remnawave_uuid:
                await set_user_remnawave_uuid(db_user.id, remnawave_uuid)
    else:
        await remnawave.update_user(
            remnawave_uuid,
            trafficLimitBytes=traffic_bytes,
            expireAt=expire_at,
        )

    # Record subscription
    sub = await create_subscription(
        user_id=db_user.id,
        vpn_type=vpn_type,
        devices=devices,
        traffic_gb=traffic_gb,
        days=days,
        price_kopecks=price_kopecks,
        remnawave_uuid=remnawave_uuid,
    )

    # Record transaction
    tx = await create_transaction(
        user_id=db_user.id,
        amount_kopecks=price_kopecks,
        type="purchase",
        description=f"{vpn_type} VPN {days} дней",
        payment_provider=payment_provider,
        payment_id=payment_id,
        status="completed",
    )

    # Get subscription link
    sub_link = None
    if remnawave_uuid:
        sub_link = await remnawave.get_user_subscription_link(remnawave_uuid)

    await state.clear()

    text = (
        "✅ <b>Подписка успешно оформлена!</b>\n\n"
        f"📋 Тариф: <b>{'Белые списки VPN' if vpn_type == 'whitelist' else 'Базовый VPN'}</b>\n"
        f"📱 Устройств: <b>{devices}</b>\n"
        f"💾 Трафик: <b>{traffic_gb} GB</b>\n"
        f"📅 Срок: <b>{days} дней</b>\n"
        f"💰 Оплачено: <b>{settings.format_price(price_kopecks)}</b>\n"
    )
    if sub_link:
        text += f"\n🔗 <b>Ссылка подключения:</b>\n<code>{sub_link}</code>"

    from bot.keyboards.user import back_button
    await _edit_or_send(callback, text, back_button("main_menu"))
    await callback.answer("✅ Подписка оформлена!", show_alert=False)


# ── Pay with YooKassa ─────────────────────────────────────────────────────────

@router.callback_query(BuyFlow.choosing_payment, F.data == "pay:yookassa")
async def cb_pay_yookassa(callback: CallbackQuery, db_user: User, state: FSMContext):
    data = await state.get_data()
    price_kopecks = data.get("price_kopecks", 0)
    extra = settings.yookassa_extra_percent
    total_kopecks = int(price_kopecks * (1 + extra / 100))

    pay_url = await _create_yookassa_payment(db_user.id, total_kopecks, data)
    if not pay_url:
        await callback.answer("❌ Ошибка создания платежа. Попробуйте позже.", show_alert=True)
        return

    text = (
        "💳 <b>Перейдите по ссылке для оплаты</b>\n\n"
        f"Сумма: <b>{settings.format_price(total_kopecks)}</b> "
        f"(включая комиссию {extra}%)\n\n"
        "После оплаты подписка будет активирована автоматически."
    )
    await _edit_or_send(callback, text, payment_link_keyboard(pay_url))
    await callback.answer()


async def _create_yookassa_payment(user_id: int, amount_kopecks: int, data: dict) -> str:
    try:
        import aiohttp, uuid
        amount_rub = amount_kopecks / 100
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.yookassa.ru/v3/payments",
                json={
                    "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                    "confirmation": {
                        "type": "redirect",
                        "return_url": "https://t.me/",
                    },
                    "capture": True,
                    "description": f"VPN {data.get('days', 30)} дней - user {user_id}",
                    "metadata": {"user_id": user_id, **data},
                },
                auth=aiohttp.BasicAuth(
                    settings.yookassa_shop_id,
                    settings.yookassa_secret_key,
                ),
                headers={
                    "Idempotence-Key": str(uuid.uuid4()),
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["confirmation"]["confirmation_url"]
    except Exception as e:
        logger.error(f"YooKassa error: {e}")
    return None
