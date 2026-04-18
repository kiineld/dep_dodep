from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛒 Купить подписку", callback_data="buy_subscription"))
    builder.row(InlineKeyboardButton(text="📋 Мои подписки", callback_data="my_subscriptions"))
    builder.row(InlineKeyboardButton(text="💰 Пополнение баланса", callback_data="topup_balance"))
    builder.row(InlineKeyboardButton(text="🎁 Промокод", callback_data="enter_promo"))
    builder.row(InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about_service"))
    return builder.as_markup()


def back_button(callback: str = "main_menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data=callback))
    return builder.as_markup()


def vpn_category_keyboard(available_servers: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🌐 Базовый VPN", callback_data="vpn_type:basic"))
    builder.row(InlineKeyboardButton(text="⚪ Белые списки VPN", callback_data="vpn_type:whitelist"))
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="main_menu"))
    return builder.as_markup()


def devices_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📱 5 Устройств | 500 GB", callback_data="devices:5:500"))
    builder.row(InlineKeyboardButton(text="📱 10 устройств | 1 ТБ", callback_data="devices:10:1024"))
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="buy_subscription"))
    return builder.as_markup()


def period_keyboard(vpn_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    premium = vpn_type == "whitelist"
    flag = "🔴 " if premium else ""

    p30 = settings.format_price(settings.get_plan_price(30, premium))
    p90 = settings.format_price(settings.get_plan_price(90, premium))
    p180 = settings.format_price(settings.get_plan_price(180, premium))
    p365 = settings.format_price(settings.get_plan_price(365, premium))

    builder.row(InlineKeyboardButton(text=f"30 дней {flag}- {p30}", callback_data="period:30"))
    builder.row(InlineKeyboardButton(text=f"90 дней {flag}- {p90}", callback_data="period:90"))
    builder.row(InlineKeyboardButton(text=f"180 дней {flag}- {p180}", callback_data="period:180"))
    builder.row(InlineKeyboardButton(text=f"365 дней {flag}- {p365}", callback_data="period:365"))
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="buy_subscription"))
    return builder.as_markup()


def payment_method_keyboard(
    yookassa: bool = False,
    cryptobot: bool = False,
    stars: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if yookassa:
        extra = f"(+{settings.yookassa_extra_percent}%)"
        builder.row(InlineKeyboardButton(
            text=f"💳 ЮКасса: СБП, Карта{extra}",
            callback_data="pay:yookassa",
        ))
    if cryptobot:
        builder.row(InlineKeyboardButton(
            text="₿ CryptoBot",
            callback_data="pay:cryptobot",
        ))
    if stars:
        builder.row(InlineKeyboardButton(
            text="⭐ Telegram Stars",
            callback_data="pay:stars",
        ))

    # Balance payment always available
    builder.row(InlineKeyboardButton(text="💼 Оплата с баланса", callback_data="pay:balance"))
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="buy_subscription"))
    return builder.as_markup()


def topup_payment_keyboard(
    yookassa: bool = False,
    cryptobot: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if yookassa:
        extra = f"(+{settings.yookassa_extra_percent}%)"
        builder.row(InlineKeyboardButton(
            text=f"💳 ЮКасса: СБП, Карта{extra}",
            callback_data="topup_pay:yookassa",
        ))
    if cryptobot:
        builder.row(InlineKeyboardButton(
            text="₿ CryptoBot",
            callback_data="topup_pay:cryptobot",
        ))

    builder.row(InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="topup_balance"))
    return builder.as_markup()


def topup_quick_amounts_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    amounts = [100, 200, 500, 1000, 2000, 5000]
    for amount in amounts:
        builder.button(
            text=f"{amount} RUB",
            callback_data=f"topup_amount:{amount * 100}",  # store in kopecks
        )
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="main_menu"))
    return builder.as_markup()


def payment_link_keyboard(url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Оплата", url=url))
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="main_menu"))
    return builder.as_markup()


def subscription_detail_keyboard(sub_id: int, has_remnawave: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_remnawave:
        builder.row(InlineKeyboardButton(text="🔗 Получить ссылку", callback_data=f"get_link:{sub_id}"))
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться назад", callback_data="my_subscriptions"))
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu"))
    return builder.as_markup()
