from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from bot.config import settings
from bot.database import User
from bot.keyboards.user import back_button
from bot.services.subscription_service import get_user_subscriptions, get_active_subscription
from bot.services.remnawave import remnawave
from bot.utils.navigation import edit_or_resend

router = Router()


@router.callback_query(F.data == "my_subscriptions")
async def cb_my_subscriptions(callback: CallbackQuery, db_user: User):
    subs = await get_user_subscriptions(db_user.id)

    if not subs:
        text = (
            "📋 <b>Мои подписки</b>\n\n"
            "У вас пока нет подписок.\n"
            "Нажмите «Купить подписку», чтобы начать!"
        )
        await edit_or_resend(callback, text, back_button("main_menu"))
        await callback.answer()
        return

    text = "📋 <b>Мои подписки</b>\n\n"
    for sub in subs[:5]:
        active = sub.status == "active" and sub.expires_at and sub.expires_at > datetime.utcnow()
        icon = "✅" if active else "❌"
        type_name = "🔵 Базовый" if sub.vpn_type == "basic" else "⚪ Белые списки"
        expires = sub.expires_at.strftime("%d.%m.%Y") if sub.expires_at else "—"
        text += (
            f"{icon} {type_name} | {sub.days} дней\n"
            f"   📱 {sub.devices} уст. | 💾 {sub.traffic_gb} GB\n"
            f"   📅 До: {expires}\n\n"
        )
    if len(subs) > 5:
        text += f"...и ещё {len(subs) - 5} подписок\n"

    # Show Remnawave usage for latest active sub
    active_sub = await get_active_subscription(db_user.id)
    if active_sub and active_sub.remnawave_uuid:
        rw_user = await remnawave.get_user(active_sub.remnawave_uuid)
        if rw_user:
            used_bytes = rw_user.get("usedTrafficBytes", 0)
            text += f"\n📊 <b>Использовано трафика:</b> {used_bytes / (1024**3):.2f} GB"

    builder = InlineKeyboardBuilder()
    if active_sub and active_sub.remnawave_uuid:
        builder.row(InlineKeyboardButton(
            text="🔗 Ссылка подключения",
            callback_data=f"get_link:{active_sub.id}",
        ))
    builder.row(InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="buy_subscription"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"))

    await edit_or_resend(callback, text, builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("get_link:"))
async def cb_get_link(callback: CallbackQuery, db_user: User):
    sub_id = int(callback.data.split(":")[1])
    subs   = await get_user_subscriptions(db_user.id)
    sub    = next((s for s in subs if s.id == sub_id), None)

    if not sub or sub.user_id != db_user.id:
        await callback.answer("❌ Подписка не найдена", show_alert=True)
        return
    if not sub.remnawave_uuid:
        await callback.answer("❌ UUID подписки не найден", show_alert=True)
        return

    link = await remnawave.get_user_subscription_link(sub.remnawave_uuid)
    if not link:
        await callback.answer("❌ Не удалось получить ссылку", show_alert=True)
        return

    text = (
        "🔗 <b>Ссылка подключения</b>\n\n"
        f"<code>{link}</code>\n\n"
        "Скопируйте ссылку и добавьте её в ваш VPN-клиент."
    )
    await edit_or_resend(callback, text, back_button("my_subscriptions"))
    await callback.answer()
