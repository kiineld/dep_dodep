from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
import logging, uuid as _uuid

from bot.config import settings
from bot.database import User
from bot.keyboards.user import payment_link_keyboard, back_button
from bot.services.subscription_service import create_transaction
from bot.services.user_service import update_user_balance
from bot.states import TopUpFlow
from bot.utils.navigation import edit_or_resend, send_photo_message

logger = logging.getLogger(__name__)
router = Router()


def _topup_amounts_kb() -> any:
    """Quick-amount buttons + back to main menu."""
    builder = InlineKeyboardBuilder()
    for amount in [100, 200, 500, 1000, 2000, 5000]:
        builder.button(text=f"{amount} RUB", callback_data=f"topup_amount:{amount * 100}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="main_menu"))
    return builder.as_markup()


def _topup_payment_kb() -> any:
    builder = InlineKeyboardBuilder()
    if settings.yookassa_enabled:
        extra = f"(+{settings.yookassa_extra_percent}%)"
        builder.row(InlineKeyboardButton(
            text=f"💳 ЮКасса: СБП, Карта {extra}",
            callback_data="topup_pay:yookassa",
        ))
    if settings.cryptobot_enabled:
        builder.row(InlineKeyboardButton(text="₿ CryptoBot", callback_data="topup_pay:cryptobot"))
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="topup_balance"))
    return builder.as_markup()


# ── Step 1: Show amount selection ─────────────────────────────────────────────

@router.callback_query(F.data == "topup_balance")
async def cb_topup_start(callback: CallbackQuery, db_user: User, state: FSMContext):
    await state.clear()
    text = (
        "💰 <b>Пополнение баланса</b>\n\n"
        f"Текущий баланс: <b>{settings.format_price(db_user.balance)}</b>\n\n"
        "Выберите сумму пополнения или введите вручную (минимум 50 RUB):"
    )
    await edit_or_resend(callback, text, _topup_amounts_kb())
    await state.set_state(TopUpFlow.entering_amount)
    await callback.answer()


# ── Quick-amount button ───────────────────────────────────────────────────────

@router.callback_query(TopUpFlow.entering_amount, F.data.startswith("topup_amount:"))
async def cb_topup_quick(callback: CallbackQuery, state: FSMContext):
    amount_kopecks = int(callback.data.split(":")[1])
    await state.update_data(amount_kopecks=amount_kopecks)
    text = (
        "💳 <b>Выберите способ пополнения баланса</b>\n\n"
        f"Сумма: <b>{settings.format_price(amount_kopecks)}</b>"
    )
    await edit_or_resend(callback, text, _topup_payment_kb())
    await state.set_state(TopUpFlow.choosing_payment)
    await callback.answer()


# ── Manual amount entry ───────────────────────────────────────────────────────

@router.message(TopUpFlow.entering_amount)
async def msg_topup_amount(message: Message, db_user: User, state: FSMContext):
    raw = message.text.strip().replace(",", ".").replace(" ", "")
    try:
        amount_rub = float(raw)
        if amount_rub < 50:
            # Delete user message, re-show the amounts screen with error note
            try:
                await message.delete()
            except Exception:
                pass
            text = (
                "💰 <b>Пополнение баланса</b>\n\n"
                f"Текущий баланс: <b>{settings.format_price(db_user.balance)}</b>\n\n"
                "❌ Минимальная сумма — <b>50 RUB</b>. Попробуйте снова:"
            )
            await send_photo_message(message, text, _topup_amounts_kb())
            return
        amount_kopecks = int(amount_rub * 100)
    except ValueError:
        try:
            await message.delete()
        except Exception:
            pass
        text = (
            "💰 <b>Пополнение баланса</b>\n\n"
            "❌ Введите корректное число (например: <code>500</code>):"
        )
        await send_photo_message(message, text, _topup_amounts_kb())
        return

    await state.update_data(amount_kopecks=amount_kopecks)
    # Delete the user's raw text message
    try:
        await message.delete()
    except Exception:
        pass
    text = (
        "💳 <b>Выберите способ пополнения баланса</b>\n\n"
        f"Сумма: <b>{settings.format_price(amount_kopecks)}</b>"
    )
    await send_photo_message(message, text, _topup_payment_kb())
    await state.set_state(TopUpFlow.choosing_payment)


# ── Pay: YooKassa ─────────────────────────────────────────────────────────────

@router.callback_query(TopUpFlow.choosing_payment, F.data == "topup_pay:yookassa")
async def cb_topup_yookassa(callback: CallbackQuery, db_user: User, state: FSMContext):
    data = await state.get_data()
    amount_kopecks = data.get("amount_kopecks", 0)
    extra = settings.yookassa_extra_percent
    total_kopecks = int(amount_kopecks * (1 + extra / 100))
    await callback.answer("⏳ Создаю счёт...")

    pay_url = await _yookassa_topup(db_user.id, total_kopecks)
    if not pay_url:
        await edit_or_resend(
            callback,
            "❌ <b>Ошибка создания платежа.</b>\n\nПроверьте настройки YooKassa или попробуйте позже.",
            back_button("topup_balance"),
        )
        return

    text = (
        "💳 <b>Перейдите по ссылке для оплаты</b>\n\n"
        f"Сумма пополнения: <b>{settings.format_price(amount_kopecks)}</b>\n"
        f"К оплате: <b>{settings.format_price(total_kopecks)}</b> "
        f"(включая комиссию {extra}%)\n\n"
        "После оплаты баланс пополнится автоматически."
    )
    await edit_or_resend(callback, text, payment_link_keyboard(pay_url))


# ── Pay: CryptoBot ────────────────────────────────────────────────────────────

@router.callback_query(TopUpFlow.choosing_payment, F.data == "topup_pay:cryptobot")
async def cb_topup_cryptobot(callback: CallbackQuery, db_user: User, state: FSMContext):
    data = await state.get_data()
    amount_kopecks = data.get("amount_kopecks", 0)
    await callback.answer("⏳ Создаю счёт...")

    pay_url = await _cryptobot_invoice(db_user.id, amount_kopecks / 100)
    if not pay_url:
        await edit_or_resend(
            callback,
            "❌ <b>Ошибка создания платежа.</b>\n\nПроверьте настройки CryptoBot или попробуйте позже.",
            back_button("topup_balance"),
        )
        return

    text = (
        "₿ <b>Оплата через CryptoBot</b>\n\n"
        f"Сумма: <b>{settings.format_price(amount_kopecks)}</b>\n\n"
        "Перейдите по ссылке для завершения оплаты:"
    )
    await edit_or_resend(callback, text, payment_link_keyboard(pay_url))


# ── YooKassa helper ───────────────────────────────────────────────────────────

async def _yookassa_topup(user_id: int, amount_kopecks: int) -> str:
    try:
        import aiohttp
        amount_rub = amount_kopecks / 100
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.yookassa.ru/v3/payments",
                json={
                    "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                    "confirmation": {"type": "redirect", "return_url": "https://t.me"},
                    "capture": True,
                    "description": f"Пополнение баланса – user {user_id}",
                    "metadata": {"user_id": str(user_id), "type": "topup"},
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
        logger.error(f"YooKassa topup error: {e}")
    return ""


# ── CryptoBot helper ──────────────────────────────────────────────────────────

async def _cryptobot_invoice(user_id: int, amount_rub: float) -> str:
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://pay.crypt.bot/api/createInvoice",
                json={
                    "asset": "USDT",
                    "amount": f"{amount_rub / 90:.4f}",   # approx RUB → USDT
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
                        url = result["result"].get("bot_invoice_url", "")
                        return url if url.startswith("https://") else ""
    except Exception as e:
        logger.error(f"CryptoBot error: {e}")
    return ""
