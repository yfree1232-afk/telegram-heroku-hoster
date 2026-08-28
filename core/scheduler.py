import logging
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.database import db
from core.heroku import heroku_client
from utils.keyboards import get_renew_keyboard

logger = logging.getLogger(__name__)

class SubscriptionScheduler:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

    def start(self):
        # Run check every 30 minutes
        self.scheduler.add_job(
            self.check_subscriptions,
            "interval",
            minutes=30,
            next_run_time=datetime.now() + timedelta(seconds=15)
        )
        self.scheduler.start()
        logger.info("Subscription scheduler started.")

    async def check_subscriptions(self):
        """Check all active apps for expiry and warnings"""
        try:
            now = datetime.utcnow()
            all_apps = await db.get_all_active_apps()

            for app in all_apps:
                if app.get("is_admin_app") or not app.get("expires_at"):
                    continue

                try:
                    expires_at = datetime.fromisoformat(app["expires_at"])
                except Exception:
                    continue

                user_id = app["user_id"]
                app_name = app["heroku_app_name"]
                display_name = app["display_name"]
                app_id = app["id"]

                # 1. Check if already EXPIRED
                if expires_at <= now and app.get("status") != "stopped":
                    logger.info(f"App {app_name} of user {user_id} expired. Stopping dynos...")
                    
                    # Stop dyno on Heroku
                    await heroku_client.scale_dyno(app_name, dyno_type=app.get("dyno_type", "worker"), quantity=0)
                    await db.update_app_status(app_id, "stopped")

                    try:
                        await self.bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"⚠️ **Your Bot Hosting Has Expired!**\n\n"
                                f"🤖 **Bot Name:** `{display_name}`\n"
                                f"🏷️ **Heroku App:** `{app_name}`\n"
                                f"📅 **Expired On:** `{expires_at.strftime('%d-%m-%Y %H:%M UTC')}`\n\n"
                                f"Your bot has been paused. Please renew your subscription to keep it running 24/7."
                            ),
                            reply_markup=get_renew_keyboard(app_id),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send expiry message to {user_id}: {e}")

                # 2. Check 1-Day Expiry Warning
                elif timedelta(hours=0) < (expires_at - now) <= timedelta(hours=24):
                    # Warning condition
                    pass # Handled in regular UI or on-demand checks

        except Exception as e:
            logger.exception(f"Error in subscription scheduler loop: {e}")
