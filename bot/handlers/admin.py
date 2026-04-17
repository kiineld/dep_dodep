from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from datetime import datetime

from bot.config import settings
from bot.database import User
from bot.keyboards.admin import (
    admin_main_keyboard,
    admin_users_keyboard,
    admin_user_actions_keyboard,
    admin_promos_keyboard,
    admin_promo_type_keyboard,
    admin_remnawave_keyboard,
    admin_back_keyboard,
    admin_payments_keyboard,
    confirm_keyboard,
)
from bot.services.user_service import (
    get_user,
    update_user_balance,
    ban_user,
    unban_user,
    get_all_users_count,
    get_all_user_ids,
)
from bot.services.subscription_service import (
    get_total_revenue,
    get_subscriptions_count,
    get_user_transactions,
)
from bot.services.promo_service import (
    create_promo_code,
    get_all_promo_codes,
    deactivate_promo_code,
)
from bot.services.remnawave import remnawave
from bot.states import AdminFlow
import logging

logger = logging.getLogger(__name__)
router = Router()

# Admin check filter
def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids_list


async def _edit_or_send(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(
            text=text, reply_markup=reply_markup, parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


# ── Entry point ───────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к панели администратора.")
        return
    await state.clear()
    await message.answer(
        "🔧 <b>Панель администратора</b>\n\nВыберите раздел:",
        reply_markup=admin_main_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin:main")
async def cb_admin_main(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await state.clear()
    await _edit_or_send(
        callback,
        "🔧 <b>Панель администратора</b>\n\nВыберите раздел:",
        admin_main_keyboard(),
    )
    await callback.answer()


# ── Statistics ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    total_users = await get_all_users_count()
    total_subs = await get_subscriptions_count()
    total_revenue = await get_total_revenue()
    rw_nodes = await remnawave.get_active_nodes_count()

    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"📋 Активных подписок: <b>{total_subs}</b>\n"
        f"💰 Общий доход: <b>{settings.format_price(total_revenue)}</b>\n"
        f"🖥️ Активных серверов: <b>{rw_nodes}</b>\n\n"
        f"🕐 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    await _edit_or_send(callback, text, admin_back_keyboard("admin:main"))
    await callback.answer()


# ── Users ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:users")
async def cb_admin_users(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await state.clear()
    await _edit_or_send(callback, "👥 <b>Управление пользователями</b>", admin_users_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:find_user")
async def cb_admin_find_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await _edit_or_send(
        callback,
        "🔍 <b>Поиск пользователя</b>\n\nВведите Telegram ID или @username:",
        admin_back_keyboard("admin:users"),
    )
    await state.set_state(AdminFlow.searching_user)
    await callback.answer()


@router.message(AdminFlow.searching_user)
async def msg_admin_search_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    query = message.text.strip().lstrip("@")
    user = None

    # Try by Telegram ID
    if query.isdigit():
        user = await get_user(int(query))

    # Try by username from DB
    if not user:
        from bot.database import async_session_maker, User as DBUser
        from sqlalchemy import select
        async with async_session_maker() as session:
            result = await session.execute(
                select(DBUser).where(DBUser.username == query)
            )
            user = result.scalar_one_or_none()

    if not user:
        await message.answer(
            "❌ Пользователь не найден.",
            reply_markup=admin_back_keyboard("admin:users"),
        )
        await state.clear()
        return

    await state.clear()
    await _show_user_info(message, user)


async def _show_user_info(target, user: User):
    name = user.first_name or "—"
    username = f"@{user.username}" if user.username else "—"
    status = "🚫 Забанен" if user.is_banned else "✅ Активен"
    text = (
        f"👤 <b>Пользователь</b>\n\n"
        f"ID: <code>{user.id}</code>\n"
        f"Имя: {name}\n"
        f"Username: {username}\n"
        f"Статус: {status}\n"
        f"💰 Баланс: <b>{settings.format_price(user.balance)}</b>\n"
        f"🗓 Регистрация: {user.created_at.strftime('%d.%m.%Y') if user.created_at else '—'}\n"
        f"🔑 Remnawave UUID: <code>{user.remnawave_uuid or '—'}</code>"
    )
    kb = admin_user_actions_keyboard(user.id, user.is_banned)
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await _edit_or_send(target, text, kb)


@router.callback_query(F.data.startswith("admin:ban:"))
async def cb_admin_ban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    await ban_user(user_id)
    await callback.answer(f"✅ Пользователь {user_id} забанен", show_alert=True)
    user = await get_user(user_id)
    if user:
        await _show_user_info(callback, user)


@router.callback_query(F.data.startswith("admin:unban:"))
async def cb_admin_unban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    await unban_user(user_id)
    await callback.answer(f"✅ Пользователь {user_id} разбанен", show_alert=True)
    user = await get_user(user_id)
    if user:
        await _show_user_info(callback, user)


@router.callback_query(F.data.startswith("admin:add_balance:"))
async def cb_admin_add_balance(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    await state.update_data(target_user_id=user_id)
    await _edit_or_send(
        callback,
        f"💰 <b>Пополнение баланса</b>\n\nПользователь: <code>{user_id}</code>\n\nВведите сумму в рублях:",
        admin_back_keyboard("admin:users"),
    )
    await state.set_state(AdminFlow.adding_balance)
    await callback.answer()


@router.message(AdminFlow.adding_balance)
async def msg_admin_add_balance(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    user_id = data.get("target_user_id")
    try:
        amount_rub = float(message.text.strip())
        amount_kopecks = int(amount_rub * 100)
        new_balance = await update_user_balance(user_id, amount_kopecks)
        await state.clear()
        await message.answer(
            f"✅ Баланс пользователя <code>{user_id}</code> пополнен на <b>{settings.format_price(amount_kopecks)}</b>\n"
            f"Новый баланс: <b>{settings.format_price(new_balance)}</b>",
            reply_markup=admin_back_keyboard("admin:users"),
            parse_mode="HTML",
        )
    except ValueError:
        await message.answer("❌ Введите корректную сумму.", reply_markup=admin_back_keyboard("admin:users"))


@router.callback_query(F.data.startswith("admin:sub_balance:"))
async def cb_admin_sub_balance(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    await state.update_data(target_user_id=user_id)
    await _edit_or_send(
        callback,
        f"➖ <b>Снятие с баланса</b>\n\nПользователь: <code>{user_id}</code>\n\nВведите сумму в рублях:",
        admin_back_keyboard("admin:users"),
    )
    await state.set_state(AdminFlow.subtracting_balance)
    await callback.answer()


@router.message(AdminFlow.subtracting_balance)
async def msg_admin_sub_balance(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    user_id = data.get("target_user_id")
    try:
        amount_rub = float(message.text.strip())
        amount_kopecks = int(amount_rub * 100)
        new_balance = await update_user_balance(user_id, -amount_kopecks)
        await state.clear()
        await message.answer(
            f"✅ С баланса пользователя <code>{user_id}</code> снято <b>{settings.format_price(amount_kopecks)}</b>\n"
            f"Новый баланс: <b>{settings.format_price(new_balance)}</b>",
            reply_markup=admin_back_keyboard("admin:users"),
            parse_mode="HTML",
        )
    except ValueError:
        await message.answer("❌ Введите корректную сумму.", reply_markup=admin_back_keyboard("admin:users"))


@router.callback_query(F.data.startswith("admin:msg_user:"))
async def cb_admin_msg_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    await state.update_data(target_user_id=user_id)
    await _edit_or_send(
        callback,
        f"📩 <b>Сообщение пользователю</b>\n\nID: <code>{user_id}</code>\n\nВведите текст сообщения:",
        admin_back_keyboard("admin:users"),
    )
    await state.set_state(AdminFlow.messaging_user)
    await callback.answer()


@router.message(AdminFlow.messaging_user)
async def msg_admin_message_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    user_id = data.get("target_user_id")
    try:
        await message.bot.send_message(
            chat_id=user_id,
            text=f"📩 <b>Сообщение от администратора:</b>\n\n{message.text}",
            parse_mode="HTML",
        )
        await message.answer(
            f"✅ Сообщение отправлено пользователю <code>{user_id}</code>",
            reply_markup=admin_back_keyboard("admin:users"),
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(
            f"❌ Не удалось отправить сообщение: {e}",
            reply_markup=admin_back_keyboard("admin:users"),
        )
    await state.clear()


@router.callback_query(F.data.startswith("admin:user_txns:"))
async def cb_admin_user_txns(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    txns = await get_user_transactions(user_id, limit=10)
    if not txns:
        await callback.answer("Транзакций нет", show_alert=True)
        return
    text = f"📋 <b>Транзакции пользователя {user_id}</b>\n\n"
    for tx in txns:
        icon = "➕" if tx.amount_kopecks > 0 else "➖"
        date = tx.created_at.strftime("%d.%m %H:%M") if tx.created_at else "—"
        text += f"{icon} {settings.format_price(abs(tx.amount_kopecks))} — {tx.description} [{date}]\n"
    await _edit_or_send(callback, text, admin_back_keyboard(f"admin:find_user"))
    await callback.answer()


# ── Promo Codes ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:promos")
async def cb_admin_promos(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await state.clear()
    await _edit_or_send(callback, "🎁 <b>Управление промокодами</b>", admin_promos_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:create_promo")
async def cb_admin_create_promo(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await _edit_or_send(
        callback,
        "🎁 <b>Создание промокода</b>\n\nВыберите тип:",
        admin_promo_type_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo_type:"))
async def cb_admin_promo_type(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    promo_type = callback.data.split(":")[2]
    await state.update_data(promo_type=promo_type)

    if promo_type == "balance":
        prompt = "Введите название промокода (латиница/цифры), затем сумму в рублях через пробел.\nПример: <code>BONUS100 100</code>"
    else:
        prompt = "Введите название промокода и количество дней через пробел.\nПример: <code>WEEK7 7</code>"

    await _edit_or_send(
        callback,
        f"🎁 <b>Создание промокода</b>\n\n{prompt}",
        admin_back_keyboard("admin:promos"),
    )
    await state.set_state(AdminFlow.creating_promo_code)
    await callback.answer()


@router.message(AdminFlow.creating_promo_code)
async def msg_admin_create_promo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    promo_type = data.get("promo_type", "balance")

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Неверный формат. Введите код и значение через пробел.")
        return

    code = parts[0].upper()
    try:
        raw_value = float(parts[1])
        value = int(raw_value * 100) if promo_type == "balance" else int(raw_value)
    except ValueError:
        await message.answer("❌ Неверное значение. Введите число.")
        return

    max_uses = 1
    if len(parts) >= 3 and parts[2].isdigit():
        max_uses = int(parts[2])

    try:
        promo = await create_promo_code(code=code, type=promo_type, value=value, max_uses=max_uses)
        type_label = "баланс" if promo_type == "balance" else "дней"
        val_display = settings.format_price(value) if promo_type == "balance" else f"{value} дн."
        await message.answer(
            f"✅ <b>Промокод создан!</b>\n\n"
            f"Код: <code>{promo.code}</code>\n"
            f"Тип: {type_label}\n"
            f"Значение: {val_display}\n"
            f"Использований: {max_uses}",
            reply_markup=admin_back_keyboard("admin:promos"),
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(
            f"❌ Ошибка создания промокода: {e}",
            reply_markup=admin_back_keyboard("admin:promos"),
        )
    await state.clear()


@router.callback_query(F.data == "admin:list_promos")
async def cb_admin_list_promos(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    promos = await get_all_promo_codes()
    if not promos:
        await callback.answer("Промокодов нет", show_alert=True)
        return
    text = "🎁 <b>Список промокодов</b>\n\n"
    for p in promos[:20]:
        status = "✅" if p.is_active else "❌"
        val = settings.format_price(p.value) if p.type == "balance" else f"{p.value} дн."
        text += f"{status} <code>{p.code}</code> — {val} [{p.used_count}/{p.max_uses}]\n"
    await _edit_or_send(callback, text, admin_back_keyboard("admin:promos"))
    await callback.answer()


@router.callback_query(F.data == "admin:deactivate_promo")
async def cb_admin_deactivate_promo(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await _edit_or_send(
        callback,
        "❌ <b>Деактивация промокода</b>\n\nВведите код промокода:",
        admin_back_keyboard("admin:promos"),
    )
    await state.set_state(AdminFlow.deactivating_promo)
    await callback.answer()


@router.message(AdminFlow.deactivating_promo)
async def msg_admin_deactivate_promo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    code = message.text.strip().upper()
    ok = await deactivate_promo_code(code)
    await state.clear()
    if ok:
        await message.answer(
            f"✅ Промокод <code>{code}</code> деактивирован.",
            reply_markup=admin_back_keyboard("admin:promos"),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"❌ Промокод <code>{code}</code> не найден.",
            reply_markup=admin_back_keyboard("admin:promos"),
            parse_mode="HTML",
        )


# ── Broadcast ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await _edit_or_send(
        callback,
        "📢 <b>Рассылка</b>\n\nВведите текст сообщения для отправки всем пользователям.\n\n"
        "<i>Поддерживается HTML форматирование</i>",
        admin_back_keyboard("admin:main"),
    )
    await state.set_state(AdminFlow.writing_broadcast)
    await callback.answer()


@router.message(AdminFlow.writing_broadcast)
async def msg_admin_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text or message.caption or ""
    user_ids = await get_all_user_ids()
    sent = 0
    failed = 0
    status_msg = await message.answer(f"📢 Начинаю рассылку... (0/{len(user_ids)})")

    for i, uid in enumerate(user_ids):
        try:
            await message.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

        if (i + 1) % 50 == 0:
            try:
                await status_msg.edit_text(
                    f"📢 Рассылка... ({i+1}/{len(user_ids)})\n✅ {sent} / ❌ {failed}"
                )
            except Exception:
                pass

    await state.clear()
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}",
        reply_markup=admin_back_keyboard("admin:main"),
        parse_mode="HTML",
    )


# ── Remnawave Integration ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:remnawave")
async def cb_admin_remnawave(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await _edit_or_send(callback, "⚙️ <b>Remnawave</b>", admin_remnawave_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:rw_health")
async def cb_admin_rw_health(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    ok = await remnawave.health_check()
    status = "✅ Подключено" if ok else "❌ Нет связи"
    url = settings.remnawave_api_url or "Не задан"
    await _edit_or_send(
        callback,
        f"🔄 <b>Статус Remnawave</b>\n\n"
        f"URL: <code>{url}</code>\n"
        f"Статус: {status}",
        admin_back_keyboard("admin:remnawave"),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:rw_nodes")
async def cb_admin_rw_nodes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    nodes = await remnawave.get_nodes()
    if not nodes:
        await callback.answer("Серверов нет или нет связи", show_alert=True)
        return
    text = "🖥️ <b>Серверы Remnawave</b>\n\n"
    for n in nodes:
        icon = "✅" if n.get("isConnected") and n.get("isEnabled") else "❌"
        name = n.get("name", "—")
        address = n.get("address", "—")
        text += f"{icon} <b>{name}</b> — <code>{address}</code>\n"
    await _edit_or_send(callback, text, admin_back_keyboard("admin:remnawave"))
    await callback.answer()


@router.callback_query(F.data == "admin:rw_stats")
async def cb_admin_rw_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    stats = await remnawave.get_system_stats()
    if not stats:
        await callback.answer("Нет данных от Remnawave", show_alert=True)
        return
    text = "📊 <b>Статистика Remnawave</b>\n\n"
    for k, v in stats.items():
        text += f"<b>{k}:</b> {v}\n"
    await _edit_or_send(callback, text, admin_back_keyboard("admin:remnawave"))
    await callback.answer()


# ── Payments ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:payments")
async def cb_admin_payments(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    text = (
        "💳 <b>Платёжные системы</b>\n\n"
        f"YooKassa: {'✅ Включена' if settings.yookassa_enabled else '❌ Выключена'}\n"
        f"CryptoBot: {'✅ Включен' if settings.cryptobot_enabled else '❌ Выключен'}\n"
        f"Telegram Stars: {'✅ Включены' if settings.telegram_stars_enabled else '❌ Выключены'}"
    )
    await _edit_or_send(callback, text, admin_payments_keyboard())
    await callback.answer()


# ── Paginated user list ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin:list_users:"))
async def cb_admin_list_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    from bot.database import async_session_maker, User as DBUser
    from sqlalchemy import select
    offset = int(callback.data.split(":")[2])
    limit = 10

    async with async_session_maker() as session:
        result = await session.execute(
            select(DBUser).order_by(DBUser.created_at.desc()).offset(offset).limit(limit)
        )
        users = result.scalars().all()

    if not users:
        await callback.answer("Пользователей нет", show_alert=True)
        return

    text = f"👥 <b>Пользователи</b> (стр. {offset//limit + 1})\n\n"
    for u in users:
        status = "🚫" if u.is_banned else "✅"
        name = u.first_name or u.username or str(u.id)
        text += f"{status} <code>{u.id}</code> — {name} | {settings.format_price(u.balance)}\n"

    builder = InlineKeyboardBuilder()
    if offset > 0:
        builder.button(text="◀️ Назад", callback_data=f"admin:list_users:{offset - limit}")
    builder.button(text="▶️ Вперёд", callback_data=f"admin:list_users:{offset + limit}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Меню", callback_data="admin:users"))

    await _edit_or_send(callback, text, builder.as_markup())
    await callback.answer()
