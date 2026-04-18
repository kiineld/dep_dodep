import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from bot.config import settings
from bot.database import User
from bot.keyboards.user import main_menu_keyboard, back_button

router = Router()


def get_banner() -> FSInputFile:
    """Return local banner photo as FSInputFile."""
    return FSInputFile(settings.banner_photo)


def get_main_menu_text(user: User) -> str:
    name = user.first_name or user.username or "Пользователь"
    last = f" {user.last_name}" if user.last_name else ""
    return (
        f"👤 <b>Профиль:</b> {name}{last}\n\n"
        f"💰 <b>Баланс:</b> {settings.format_price(user.balance)}\n\n"
        f"📣 Наш канал: @{settings.bot_name.replace(' ', '_')}\n"
        f"🛟 Поддержка: @support"
    )


async def send_main_menu(target, db_user: User):
    """Send or edit the main menu photo+caption message."""
    text = get_main_menu_text(db_user)
    kb = main_menu_keyboard()

    if isinstance(target, Message):
        await target.answer_photo(
            photo=get_banner(),
            caption=text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    elif isinstance(target, CallbackQuery):
        try:
            # Try to just edit the caption (photo already shown)
            await target.message.edit_caption(
                caption=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
        except Exception:
            # If the previous message had no photo, send a new one
            await target.message.answer_photo(
                photo=get_banner(),
                caption=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
            try:
                await target.message.delete()
            except Exception:
                pass


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, state: FSMContext):
    await state.clear()
    if db_user.is_banned:
        await message.answer("🚫 Ваш аккаунт заблокирован. Обратитесь в поддержку.")
        return
    await send_main_menu(message, db_user)


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, db_user: User, state: FSMContext):
    await state.clear()
    if db_user.is_banned:
        await callback.answer("🚫 Вы заблокированы", show_alert=True)
        return
    await send_main_menu(callback, db_user)
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
        await callback.message.answer(
            text, reply_markup=back_button("main_menu"), parse_mode="HTML"
        )
    await callback.answer()
