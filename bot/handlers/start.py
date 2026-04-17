from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from bot.config import settings
from bot.database import User
from bot.keyboards.user import main_menu_keyboard, back_button
from bot.services.subscription_service import get_active_subscription

router = Router()


def get_main_menu_text(user: User, balance: int = None) -> str:
    bal = balance if balance is not None else user.balance
    name = user.first_name or user.username or "Пользователь"
    last = f" {user.last_name}" if user.last_name else ""
    username_str = f"@{user.username}" if user.username else "—"

    return (
        f"👤 <b>Профиль:</b> {name}{last}\n\n"
        f"💰 <b>Баланс:</b> {settings.format_price(bal)}\n\n"
        f"📣 Наш канал: @{settings.bot_name.replace(' ', '_')}\n"
        f"🛟 Поддержка: @support"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, state: FSMContext):
    await state.clear()
    if db_user.is_banned:
        await message.answer("🚫 Ваш аккаунт заблокирован. Обратитесь в поддержку.")
        return

    text = get_main_menu_text(db_user)
    await message.answer_photo(
        photo="https://i.imgur.com/ZfKtBVM.jpeg",  # fallback photo
        caption=text,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, db_user: User, state: FSMContext):
    await state.clear()
    if db_user.is_banned:
        await callback.answer("🚫 Вы заблокированы", show_alert=True)
        return

    text = get_main_menu_text(db_user)
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer_photo(
            photo="assets/logo.jpg",
            caption=text,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data == "about_service")
async def cb_about(callback: CallbackQuery):
    text = (
        "ℹ️ <b>О сервисе</b>\n\n"
        "🌐 Мы предоставляем надёжный VPN-сервис на базе Remnawave.\n\n"
        "✅ <b>Преимущества:</b>\n"
        "• Высокая скорость соединения\n"
        "• Несколько серверов на выбор\n"
        "• Поддержка до 10 устройств\n"
        "• Базовый и Premium (Белые списки) тарифы\n\n"
        "📱 <b>Поддерживаемые устройства:</b>\n"
        "iOS, Android, Windows, macOS, Linux\n\n"
        "🛟 По всем вопросам: @support"
    )
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=back_button("main_menu"),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(text, reply_markup=back_button("main_menu"), parse_mode="HTML")
    await callback.answer()
