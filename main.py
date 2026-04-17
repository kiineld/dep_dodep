import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.database import create_tables
from bot.middlewares.user import UserMiddleware
from bot.handlers import start, buy, balance, subscriptions, promo, admin
from bot.services.remnawave import remnawave

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    logger.info("Bot is starting up...")
    os.makedirs("data", exist_ok=True)
    await create_tables()
    logger.info("Database tables created/verified.")

    # Check Remnawave connection
    ok = await remnawave.health_check()
    if ok:
        logger.info("✅ Remnawave API connected successfully.")
    else:
        logger.warning("⚠️  Remnawave API is not reachable. Check REMNAWAVE_API_URL and REMNAWAVE_API_KEY.")

    # Notify admins on startup
    if settings.admin_notifications_enabled and settings.admin_ids_list:
        for admin_id in settings.admin_ids_list:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=(
                        "🤖 <b>Бот запущен!</b>\n\n"
                        f"🌐 Remnawave: {'✅ OK' if ok else '❌ Недоступен'}\n"
                        f"⚙️ Режим: {settings.bot_run_mode}"
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Could not notify admin {admin_id}: {e}")


async def on_shutdown(bot: Bot):
    logger.info("Bot is shutting down...")
    await remnawave.close()


async def main():
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Middlewares
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())

    # Routers
    dp.include_router(admin.router)      # Admin first (priority)
    dp.include_router(start.router)
    dp.include_router(buy.router)
    dp.include_router(balance.router)
    dp.include_router(subscriptions.router)
    dp.include_router(promo.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    if settings.bot_run_mode == "webhook":
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        from aiohttp import web

        async def handle_webhook(request):
            return web.Response(text="OK")

        app = web.Application()
        webhook_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=settings.webhook_secret_token or None,
        )
        webhook_handler.register(app, path=settings.webhook_path)
        setup_application(app, dp, bot=bot)

        await bot.set_webhook(
            url=f"{settings.webhook_url}{settings.webhook_path}",
            secret_token=settings.webhook_secret_token or None,
            drop_pending_updates=True,
        )
        logger.info(f"Webhook set: {settings.webhook_url}{settings.webhook_path}")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8080)
        await site.start()
        logger.info("Webhook server started on port 8080")

        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()
    else:
        logger.info("Starting polling mode...")
        await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
