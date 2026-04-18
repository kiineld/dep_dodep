from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.database import User
from bot.keyboards.user import back_button
from bot.services.promo_service import apply_promo_code
from bot.states import PromoFlow
from bot.utils.navigation import edit_or_resend, send_photo_message

router = Router()

_CANCEL_KB = back_button("main_menu")


@router.callback_query(F.data == "enter_promo")
async def cb_enter_promo(callback: CallbackQuery, state: FSMContext):
    text = (
        "🎁 <b>Введите промокод</b>\n\n"
        "Введите ваш промокод в поле ниже:"
    )
    await edit_or_resend(callback, text, _CANCEL_KB)
    await state.set_state(PromoFlow.entering_code)
    await callback.answer()


@router.message(PromoFlow.entering_code)
async def msg_promo_code(message: Message, db_user: User, state: FSMContext):
    code = message.text.strip()
    success, result_text = await apply_promo_code(code, db_user.id)
    await state.clear()
    # Delete user's text message, send photo reply
    try:
        await message.delete()
    except Exception:
        pass
    await send_photo_message(message, result_text, back_button("main_menu"))
