import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.database import create_tables
from bot.middlewares.user import UserMiddleware
from bot.handlers import start, buy, balance, subscriptions, promo, admin
from bot.services.remnawave import remnawave


# ── Logging ───────────────────────────────────────────────────────────────────

os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)
os.makedirs("assets", exist_ok=True)

_log_handlers = [logging.StreamHandler()]
try:
    _log_handlers.append(
        RotatingFileHandler(
            "data/bot.log",
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
    )
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_log_handlers,
)
logger = logging.getLogger(__name__)


# ── Lifecycle hooks ───────────────────────────────────────────────────────────

async def on_startup(bot: Bot):
    logger.info("Bot is starting up…")
    await create_tables()
    logger.info("Database tables created/verified.")

    ok = await remnawave.health_check()
    logger.info("Remnawave API: %s", "✅ connected" if ok else "⚠️  unreachable")

    if settings.admin_notifications_enabled:
        for admin_id in settings.admin_ids_list:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=(
                        "🤖 <b>Бот запущен!</b>\n\n"
                        f"🌐 Remnawave: {'✅ OK' if ok else '❌ Недоступен'}\n"
                        f"⚙️ Режим: <b>{settings.bot_run_mode}</b>"
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Could not notify admin {admin_id}: {e}")


async def on_shutdown(bot: Bot):
    logger.info("Bot is shutting down…")
    await remnawave.close()


# ── Bot factory ───────────────────────────────────────────────────────────────

def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())
    # Admin router first so admin callbacks take priority
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(buy.router)
    dp.include_router(balance.router)
    dp.include_router(subscriptions.router)
    dp.include_router(promo.router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    return dp


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()

    if settings.bot_run_mode == "webhook":
        if not settings.webhook_url or not settings.webhook_url.startswith("https://"):
            logger.error(
                "BOT_RUN_MODE=webhook but WEBHOOK_URL is empty or not https://. "
                "Fix your .env or switch to BOT_RUN_MODE=polling."
            )
            return

        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        from aiohttp import web

        app = web.Application()
        handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=settings.webhook_secret_token or None,
        )
        handler.register(app, path=settings.webhook_path)
        setup_application(app, dp, bot=bot)

        webhook_url = f"{settings.webhook_url.rstrip('/')}{settings.webhook_path}"
        await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret_token or None,
            drop_pending_updates=True,
        )
        logger.info(f"Webhook set: {webhook_url}")

        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", 8080).start()
        logger.info("Webhook server listening on :8080")
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()
    else:
        logger.info("Starting polling…")
        await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user.")
