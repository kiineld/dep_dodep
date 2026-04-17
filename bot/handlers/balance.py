from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.config import settings
from bot.database import User
from bot.keyboards.user import (
    topup_quick_amounts_keyboard,
    topup_payment_keyboard,
    payment_link_keyboard,
    back_button,
    cancel_keyboard,
)
from bot.services.subscription_service import create_transaction
from bot.services.user_service import update_user_balance
from bot.states import TopUpFlow
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


# ── Step 1: Show amount entry screen ─────────────────────────────────────────

@router.callback_query(F.data == "topup_balance")
async def cb_topup_start(callback: CallbackQuery, db_user: User, state: FSMContext):
    await state.clear()
    text = (
        "💰 <b>Пополнение баланса</b>\n\n"
        f"Текущий баланс: <b>{settings.format_price(db_user.balance)}</b>\n\n"
        "Выберите сумму или введите вручную (минимум 50 RUB):"
    )
    await _edit_or_send(callback, text, topup_quick_amounts_keyboard())
    await state.set_state(TopUpFlow.entering_amount)
    await callback.answer()


# ── Quick amount selection ────────────────────────────────────────────────────

@router.callback_query(TopUpFlow.entering_amount, F.data.startswith("topup_amount:"))
async def cb_topup_quick_amount(callback: CallbackQuery, db_user: User, state: FSMContext):
    amount_kopecks = int(callback.data.split(":")[1])
    await state.update_data(amount_kopecks=amount_kopecks)
    await _show_payment_choice(callback, db_user, state, amount_kopecks)
    await callback.answer()


# ── Manual amount entry ───────────────────────────────────────────────────────

@router.message(TopUpFlow.entering_amount)
async def msg_topup_amount(message: Message, db_user: User, state: FSMContext):
    text = message.text.strip().replace(",", ".").replace(" ", "")
    try:
        amount_rub = float(text)
        if amount_rub < 50:
            await message.answer(
                "❌ Минимальная сумма пополнения — 50 RUB.",
                reply_markup=cancel_keyboard(),
            )
            return
        amount_kopecks = int(amount_rub * 100)
    except ValueError:
        await message.answer(
            "❌ Введите корректную сумму (например: <code>500</code>)",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML",
        )
        return

    await state.update_data(amount_kopecks=amount_kopecks)

    kb = topup_payment_keyboard(
        yookassa=settings.yookassa_enabled,
        cryptobot=settings.cryptobot_enabled,
    )
    text = (
        f"💳 <b>Выберите способ пополнения баланса</b>\n\n"
        f"Сумма: <b>{settings.format_price(amount_kopecks)}</b>"
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(TopUpFlow.choosing_payment)


async def _show_payment_choice(
    callback: CallbackQuery,
    db_user: User,
    state: FSMContext,
    amount_kopecks: int,
):
    kb = topup_payment_keyboard(
        yookassa=settings.yookassa_enabled,
        cryptobot=settings.cryptobot_enabled,
    )
    text = (
        "💳 <b>Выберите способ пополнения баланса</b>\n\n"
        f"Сумма: <b>{settings.format_price(amount_kopecks)}</b>"
    )
    await _edit_or_send(callback, text, kb)
    await state.set_state(TopUpFlow.choosing_payment)


# ── YooKassa top-up ───────────────────────────────────────────────────────────

@router.callback_query(TopUpFlow.choosing_payment, F.data == "topup_pay:yookassa")
async def cb_topup_yookassa(callback: CallbackQuery, db_user: User, state: FSMContext):
    data = await state.get_data()
    amount_kopecks = data.get("amount_kopecks", 0)
    extra = settings.yookassa_extra_percent
    total_kopecks = int(amount_kopecks * (1 + extra / 100))

    pay_url = await _create_yookassa_topup(db_user.id, total_kopecks)
    if not pay_url:
        await callback.answer("❌ Ошибка создания платежа. Попробуйте позже.", show_alert=True)
        return

    text = (
        "💳 <b>Перейдите по ссылке для оплаты</b>\n\n"
        f"Сумма пополнения: <b>{settings.format_price(amount_kopecks)}</b>\n"
        f"К оплате: <b>{settings.format_price(total_kopecks)}</b> "
        f"(включая комиссию {extra}%)\n\n"
        "После оплаты баланс пополнится автоматически."
    )
    await _edit_or_send(callback, text, payment_link_keyboard(pay_url))
    await callback.answer()


async def _create_yookassa_topup(user_id: int, amount_kopecks: int) -> str:
    try:
        import aiohttp, uuid as uuidlib
        amount_rub = amount_kopecks / 100
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.yookassa.ru/v3/payments",
                json={
                    "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                    "confirmation": {"type": "redirect", "return_url": "https://t.me/"},
                    "capture": True,
                    "description": f"Пополнение баланса - user {user_id}",
                    "metadata": {"user_id": user_id, "type": "topup"},
                },
                auth=aiohttp.BasicAuth(
                    settings.yookassa_shop_id,
                    settings.yookassa_secret_key,
                ),
                headers={
                    "Idempotence-Key": str(uuidlib.uuid4()),
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["confirmation"]["confirmation_url"]
    except Exception as e:
        logger.error(f"YooKassa topup error: {e}")
    return None


# ── CryptoBot top-up ──────────────────────────────────────────────────────────

@router.callback_query(TopUpFlow.choosing_payment, F.data == "topup_pay:cryptobot")
async def cb_topup_cryptobot(callback: CallbackQuery, db_user: User, state: FSMContext):
    data = await state.get_data()
    amount_kopecks = data.get("amount_kopecks", 0)
    amount_rub = amount_kopecks / 100

    pay_url = await _create_cryptobot_invoice(db_user.id, amount_rub)
    if not pay_url:
        await callback.answer("❌ Ошибка создания платежа. Попробуйте позже.", show_alert=True)
        return

    text = (
        "₿ <b>Оплата через CryptoBot</b>\n\n"
        f"Сумма: <b>{settings.format_price(amount_kopecks)}</b>\n\n"
        "Перейдите по ссылке для завершения оплаты:"
    )
    await _edit_or_send(callback, text, payment_link_keyboard(pay_url))
    await callback.answer()


async def _create_cryptobot_invoice(user_id: int, amount_rub: float) -> str:
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://pay.crypt.bot/api/createInvoice",
                json={
                    "asset": "USDT",
                    "amount": f"{amount_rub / 90:.2f}",  # approx RUB→USDT
                    "description": f"Balance top-up user {user_id}",
                    "payload": str(user_id),
                    "allow_comments": False,
                    "allow_anonymous": False,
                },
                headers={"Crypto-Pay-API-Token": settings.cryptobot_api_token},
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("ok"):
                        return result["result"]["bot_invoice_url"]
    except Exception as e:
        logger.error(f"CryptoBot error: {e}")
    return None
