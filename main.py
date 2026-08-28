import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config
from core.database import db
from core.scheduler import SubscriptionScheduler

# Import routers
from handlers import common
from handlers.user import dashboard as user_dashboard
from handlers.user import billing as user_billing
from handlers.user import deploy as user_deploy
from handlers.user import manage as user_manage
from handlers.admin import panel as admin_panel
from handlers.admin import payments as admin_payments
from handlers.admin import manage_all as admin_manage_all
from handlers.admin import broadcast as admin_broadcast

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

async def main():
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in environment or .env file! Exiting...")
        return

    logger.info("Initializing Database...")
    await db.init()

    # Initialize Bot & Dispatcher
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register all handler routers
    dp.include_router(common.router)
    dp.include_router(user_dashboard.router)
    dp.include_router(user_billing.router)
    dp.include_router(user_deploy.router)
    dp.include_router(user_manage.router)
    dp.include_router(admin_panel.router)
    dp.include_router(admin_payments.router)
    dp.include_router(admin_manage_all.router)
    dp.include_router(admin_broadcast.router)

    # Start Background Subscription Expiry Scheduler
    scheduler = SubscriptionScheduler(bot)
    scheduler.start()

    logger.info("Starting Telegram Heroku Hoster Bot...")
    try:
        # Delete webhook to prevent conflicts with polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
