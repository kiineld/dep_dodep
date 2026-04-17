from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"))
    builder.row(InlineKeyboardButton(text="🎁 Промокоды", callback_data="admin:promos"))
    builder.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast"))
    builder.row(InlineKeyboardButton(text="⚙️ Remnawave", callback_data="admin:remnawave"))
    builder.row(InlineKeyboardButton(text="💳 Платёжные системы", callback_data="admin:payments"))
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def admin_users_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin:find_user"))
    builder.row(InlineKeyboardButton(text="📋 Все пользователи", callback_data="admin:list_users:0"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def admin_user_actions_keyboard(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="➕ Пополнить баланс",
        callback_data=f"admin:add_balance:{user_id}",
    ))
    builder.row(InlineKeyboardButton(
        text="➖ Снять с баланса",
        callback_data=f"admin:sub_balance:{user_id}",
    ))
    if is_banned:
        builder.row(InlineKeyboardButton(
            text="✅ Разбанить",
            callback_data=f"admin:unban:{user_id}",
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🚫 Забанить",
            callback_data=f"admin:ban:{user_id}",
        ))
    builder.row(InlineKeyboardButton(
        text="📩 Написать сообщение",
        callback_data=f"admin:msg_user:{user_id}",
    ))
    builder.row(InlineKeyboardButton(
        text="📋 История транзакций",
        callback_data=f"admin:user_txns:{user_id}",
    ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:users"))
    return builder.as_markup()


def admin_promos_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin:create_promo"))
    builder.row(InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin:list_promos"))
    builder.row(InlineKeyboardButton(text="❌ Деактивировать", callback_data="admin:deactivate_promo"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def admin_promo_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Баланс (руб)", callback_data="admin:promo_type:balance"))
    builder.row(InlineKeyboardButton(text="📅 Дни подписки", callback_data="admin:promo_type:days"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:promos"))
    return builder.as_markup()


def admin_remnawave_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🖥️ Серверы (ноды)", callback_data="admin:rw_nodes"))
    builder.row(InlineKeyboardButton(text="📊 Статистика системы", callback_data="admin:rw_stats"))
    builder.row(InlineKeyboardButton(text="🔄 Проверить связь", callback_data="admin:rw_health"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def admin_back_keyboard(target: str = "admin:main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=target))
    return builder.as_markup()


def admin_payments_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 YooKassa", callback_data="admin:pay_yookassa"))
    builder.row(InlineKeyboardButton(text="₿ CryptoBot", callback_data="admin:pay_cryptobot"))
    builder.row(InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="admin:pay_stars"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def confirm_keyboard(yes_cb: str, no_cb: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=yes_cb),
        InlineKeyboardButton(text="❌ Нет", callback_data=no_cb),
    )
    return builder.as_markup()
