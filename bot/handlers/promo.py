from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.database import User
from bot.keyboards.user import back_button, cancel_keyboard
from bot.services.promo_service import apply_promo_code
from bot.states import PromoFlow

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


@router.callback_query(F.data == "enter_promo")
async def cb_enter_promo(callback: CallbackQuery, state: FSMContext):
    text = (
        "🎁 <b>Введите промокод</b>\n\n"
        "Введите ваш промокод в поле ниже:"
    )
    await _edit_or_send(callback, text, cancel_keyboard())
    await state.set_state(PromoFlow.entering_code)
    await callback.answer()


@router.message(PromoFlow.entering_code)
async def msg_promo_code(message: Message, db_user: User, state: FSMContext):
    code = message.text.strip()
    success, msg = await apply_promo_code(code, db_user.id)
    await state.clear()
    await message.answer(
        msg,
        reply_markup=back_button("main_menu"),
        parse_mode="HTML",
    )
