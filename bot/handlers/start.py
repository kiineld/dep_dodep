from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from bot.config import settings
from bot.database import User
from bot.keyboards.user import main_menu_keyboard, back_button
from bot.utils.navigation import send_photo_message, edit_or_resend

router = Router()


def get_main_menu_text(user: User) -> str:
    name = user.first_name or user.username or "Пользователь"
    last = f" {user.last_name}" if user.last_name else ""
    return (
        f"👤 <b>Профиль:</b> {name}{last}\n\n"
        f"💰 <b>Баланс:</b> {settings.format_price(user.balance)}\n\n"
        f"📣 Наш канал: @{settings.bot_name.replace(' ', '_')}\n"
        f"🛟 Поддержка: @support"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, state: FSMContext):
    await state.clear()
    if db_user.is_banned:
        await message.answer("🚫 Ваш аккаунт заблокирован. Обратитесь в поддержку.")
        return
    await send_photo_message(message, get_main_menu_text(db_user), main_menu_keyboard())


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, db_user: User, state: FSMContext):
    await state.clear()
    if db_user.is_banned:
        await callback.answer("🚫 Вы заблокированы", show_alert=True)
        return
    await edit_or_resend(callback, get_main_menu_text(db_user), main_menu_keyboard())
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
    await edit_or_resend(callback, text, back_button("main_menu"))
    await callback.answer()
