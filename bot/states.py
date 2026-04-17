from aiogram.fsm.state import State, StatesGroup


class BuyFlow(StatesGroup):
    choosing_category = State()
    choosing_devices = State()
    choosing_period = State()
    choosing_payment = State()
    waiting_promo = State()


class TopUpFlow(StatesGroup):
    entering_amount = State()
    choosing_payment = State()


class PromoFlow(StatesGroup):
    entering_code = State()


class AdminFlow(StatesGroup):
    # User management
    searching_user = State()
    adding_balance = State()
    subtracting_balance = State()
    messaging_user = State()

    # Promo management
    creating_promo_code = State()
    creating_promo_value = State()
    creating_promo_uses = State()
    deactivating_promo = State()

    # Broadcast
    writing_broadcast = State()

    # Awaiting confirmation
    confirming = State()
