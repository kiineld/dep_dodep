from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import logging

from bot.config import settings
from bot.database import User
from bot.keyboards.user import (
    vpn_category_keyboard,
    devices_keyboard,
    period_keyboard,
    payment_method_keyboard,
    payment_link_keyboard,
    back_button,
)
from bot.services.remnawave import remnawave
from bot.services.subscription_service import create_subscription, create_transaction
from bot.services.user_service import update_user_balance, set_user_remnawave_uuid
from bot.states import BuyFlow
from bot.utils.navigation import edit_or_resend

logger = logging.getLogger(__name__)
router = Router()


# ── Step 1: Choose VPN category ───────────────────────────────────────────────

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
    await edit_or_resend(callback, text, vpn_category_keyboard(count))
    await state.set_state(BuyFlow.choosing_category)
    await callback.answer()


# ── Step 2: Choose devices ────────────────────────────────────────────────────

@router.callback_query(BuyFlow.choosing_category, F.data.startswith("vpn_type:"))
async def cb_vpn_type(callback: CallbackQuery, state: FSMContext):
    vpn_type = callback.data.split(":")[1]
    await state.update_data(vpn_type=vpn_type)
    count = await remnawave.get_active_nodes_count()
    type_name = "Базовый VPN" if vpn_type == "basic" else "Белые списки VPN"
    text = (
        f"📱 <b>Выберите максимальное количество устройств</b>\n\n"
        f"Тариф: <b>{type_name}</b>\n"
        f"Доступных серверов — <b>{count}</b>"
    )
    await edit_or_resend(callback, text, devices_keyboard())
    await state.set_state(BuyFlow.choosing_devices)
    await callback.answer()


# ── Step 3: Choose period ─────────────────────────────────────────────────────

@router.callback_query(BuyFlow.choosing_devices, F.data.startswith("devices:"))
async def cb_devices(callback: CallbackQuery, state: FSMContext):
    _, devices_str, traffic_str = callback.data.split(":")
    await state.update_data(devices=int(devices_str), traffic_gb=int(traffic_str))
    data = await state.get_data()
    vpn_type = data.get("vpn_type", "basic")
    count = await remnawave.get_active_nodes_count()
    text = (
        "📅 <b>Выберите как часто вы планируете оплачивать наш сервис</b>\n\n"
        f"Доступных серверов — <b>{count}</b>"
    )
    await edit_or_resend(callback, text, period_keyboard(vpn_type))
    await state.set_state(BuyFlow.choosing_period)
    await callback.answer()


# ── Step 4: Choose payment method ─────────────────────────────────────────────

@router.callback_query(BuyFlow.choosing_period, F.data.startswith("period:"))
async def cb_period(callback: CallbackQuery, db_user: User, state: FSMContext):
    days = int(callback.data.split(":")[1])
    data = await state.get_data()
    vpn_type = data.get("vpn_type", "basic")
    price_kopecks = settings.get_plan_price(days, vpn_type == "whitelist")
    await state.update_data(days=days, price_kopecks=price_kopecks)

    text = (
        "💳 <b>Перейдите по ссылке для оплаты</b>\n\n"
        f"Тариф: <b>{'Белые списки VPN' if vpn_type == 'whitelist' else 'Базовый VPN'}</b>\n"
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
    await edit_or_resend(callback, text, kb)
    await state.set_state(BuyFlow.choosing_payment)
    await callback.answer()


# ── Pay: balance ──────────────────────────────────────────────────────────────

@router.callback_query(BuyFlow.choosing_payment, F.data == "pay:balance")
async def cb_pay_balance(callback: CallbackQuery, db_user: User, state: FSMContext):
    data = await state.get_data()
    price_kopecks = data.get("price_kopecks", 0)
    if db_user.balance < price_kopecks:
        shortage = price_kopecks - db_user.balance
        text = (
            "❌ <b>Недостаточно средств на балансе</b>\n\n"
            f"Необходимо: <b>{settings.format_price(price_kopecks)}</b>\n"
            f"На балансе: <b>{settings.format_price(db_user.balance)}</b>\n"
            f"Не хватает: <b>{settings.format_price(shortage)}</b>\n\n"
            "Пополните баланс и попробуйте снова."
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup_balance"))
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_subscription"))
        await edit_or_resend(callback, text, builder.as_markup())
        await callback.answer()
        return
    await _do_purchase(callback, db_user, state, payment_provider="balance")


# ── Pay: YooKassa ─────────────────────────────────────────────────────────────

@router.callback_query(BuyFlow.choosing_payment, F.data == "pay:yookassa")
async def cb_pay_yookassa(callback: CallbackQuery, db_user: User, state: FSMContext):
    data = await state.get_data()
    price_kopecks = data.get("price_kopecks", 0)
    extra = settings.yookassa_extra_percent
    total_kopecks = int(price_kopecks * (1 + extra / 100))
    await callback.answer("⏳ Создаю счёт...")

    pay_url = await _yookassa_payment(db_user.id, total_kopecks, data)
    if not pay_url:
        await edit_or_resend(
            callback,
            "❌ <b>Ошибка создания платежа.</b>\n\nПроверьте настройки YooKassa или попробуйте позже.",
            back_button("buy_subscription"),
        )
        return

    text = (
        "💳 <b>Перейдите по ссылке для оплаты</b>\n\n"
        f"Сумма: <b>{settings.format_price(total_kopecks)}</b> "
        f"(включая комиссию {extra}%)\n\n"
        "После оплаты подписка будет активирована автоматически."
    )
    await edit_or_resend(callback, text, payment_link_keyboard(pay_url))


# ── Core purchase logic ───────────────────────────────────────────────────────

async def _do_purchase(
    callback: CallbackQuery,
    db_user: User,
    state: FSMContext,
    payment_provider: str,
    payment_id: str = None,
):
    data = await state.get_data()
    vpn_type      = data.get("vpn_type", "basic")
    devices       = data.get("devices", 5)
    traffic_gb    = data.get("traffic_gb", 500)
    days          = data.get("days", 30)
    price_kopecks = data.get("price_kopecks", 0)

    # 1. Deduct balance
    if payment_provider == "balance":
        await update_user_balance(db_user.id, -price_kopecks)

    # 2. Create / update Remnawave user
    remnawave_uuid = db_user.remnawave_uuid
    traffic_bytes  = traffic_gb * 1024 * 1024 * 1024
    expire_at      = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    if not remnawave_uuid:
        username = db_user.username or f"user_{db_user.id}"
        rw_user  = await remnawave.create_user(
            telegram_id=db_user.id,
            username=username,
            traffic_limit_bytes=traffic_bytes,
            expire_at=expire_at,
            description=f"Bot: {vpn_type} {days}d",
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

    # 3. Assign internal squads
    squad_ok = True
    if remnawave_uuid and (settings.basic_squad_uuid or settings.whitelist_squad_uuid):
        squad_ok = await remnawave.assign_squads_for_vpn_type(
            user_uuid=remnawave_uuid,
            vpn_type=vpn_type,
            basic_squad_uuid=settings.basic_squad_uuid,
            whitelist_squad_uuid=settings.whitelist_squad_uuid,
        )
        if not squad_ok:
            logger.warning(f"Squad assignment failed for user {db_user.id}")

    # 4. Record subscription + transaction
    await create_subscription(
        user_id=db_user.id, vpn_type=vpn_type, devices=devices,
        traffic_gb=traffic_gb, days=days, price_kopecks=price_kopecks,
        remnawave_uuid=remnawave_uuid,
    )
    await create_transaction(
        user_id=db_user.id, amount_kopecks=price_kopecks, type="purchase",
        description=f"{vpn_type} VPN {days} дней",
        payment_provider=payment_provider, payment_id=payment_id,
        status="completed",
    )

    # 5. Get subscription link
    sub_link = None
    if remnawave_uuid:
        sub_link = await remnawave.get_user_subscription_link(remnawave_uuid)

    await state.clear()

    type_label = "Белые списки VPN" if vpn_type == "whitelist" else "Базовый VPN"
    text = (
        "✅ <b>Подписка успешно оформлена!</b>\n\n"
        f"📋 Тариф: <b>{type_label}</b>\n"
        f"📱 Устройств: <b>{devices}</b>\n"
        f"💾 Трафик: <b>{traffic_gb} GB</b>\n"
        f"📅 Срок: <b>{days} дней</b>\n"
        f"💰 Оплачено: <b>{settings.format_price(price_kopecks)}</b>"
    )
    if sub_link:
        text += f"\n\n🔗 <b>Ссылка подключения:</b>\n<code>{sub_link}</code>"
    if not squad_ok and (settings.basic_squad_uuid or settings.whitelist_squad_uuid):
        text += "\n\n⚠️ Не удалось назначить сервер автоматически. Обратитесь в поддержку."

    await edit_or_resend(callback, text, back_button("main_menu"))
    await callback.answer("✅ Подписка оформлена!")


# ── YooKassa helper ───────────────────────────────────────────────────────────

async def _yookassa_payment(user_id: int, amount_kopecks: int, data: dict) -> str:
    try:
        import aiohttp, uuid as _uuid
        amount_rub = amount_kopecks / 100
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.yookassa.ru/v3/payments",
                json={
                    "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                    "confirmation": {"type": "redirect", "return_url": "https://t.me"},
                    "capture": True,
                    "description": f"VPN {data.get('days', 30)} дней – user {user_id}",
                    "metadata": {"user_id": str(user_id)},
                },
                auth=aiohttp.BasicAuth(
                    settings.yookassa_shop_id,
                    settings.yookassa_secret_key,
                ),
                headers={
                    "Idempotence-Key": str(_uuid.uuid4()),
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status in (200, 201):
                    result = await resp.json()
                    url = result.get("confirmation", {}).get("confirmation_url", "")
                    return url if url.startswith("https://") else ""
    except Exception as e:
        logger.error(f"YooKassa error: {e}")
    return ""
