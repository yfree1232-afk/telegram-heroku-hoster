import logging
import asyncio
from typing import Dict, Any, List, Tuple
from aiogram import Bot
from config import config
from core.database import db
from core.heroku import HerokuAPI
from utils.helpers import github_repo_to_tarball
import re
import random
import string

logger = logging.getLogger(__name__)

def make_safe_heroku_name(name: str) -> str:
    cleaned = re.sub(r'[^a-z0-9-]', '', name.lower().replace(" ", "-"))
    if len(cleaned) < 3:
        cleaned = "bot-host"
    rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{cleaned[:20]}-{rand_suffix}"

class DisasterRecoveryEngine:
    """
    Automatic Migration & Auto-Restore Engine:
    If a Heroku account is banned/suspended or a new Heroku API Key is provided,
    this engine automatically redeploys ALL client bots from MongoDB onto the new Heroku account.
    """
    @staticmethod
    async def restore_all_bots(new_api_key: str, bot: Bot) -> Tuple[int, int, List[str]]:
        new_client = HerokuAPI(api_key=new_api_key)
        
        # Verify new API key
        ok, acc = await new_client.get_account()
        if not ok:
            return 0, 0, [f"Invalid API Key: {acc}"]

        all_apps = await db.get_all_active_apps()
        success_count = 0
        fail_count = 0
        logs = []

        for app in all_apps:
            # Skip stopped or deleted apps if desired, or restore active ones
            if app.get("status") == "stopped" and not app.get("is_admin_app"):
                continue

            app_id = app["id"]
            user_id = app["user_id"]
            display_name = app["display_name"]
            repo_url = app.get("repo_url")
            config_vars = app.get("config_vars", {})
            dyno_type = app.get("dyno_type", "worker")

            new_app_name = make_safe_heroku_name(display_name)
            logger.info(f"Auto-Restoring {display_name} as {new_app_name} on new Heroku account...")

            # 1. Create App on New Account
            ok_c, res_c = await new_client.create_app(new_app_name)
            if not ok_c:
                fail_count += 1
                logs.append(f"❌ {display_name}: App creation failed ({res_c})")
                continue

            # 2. Apply Config Vars
            if config_vars:
                await new_client.update_config_vars(new_app_name, config_vars)

            # 3. Deploy Build from GitHub Repo
            if repo_url:
                tarball_url = github_repo_to_tarball(repo_url) or repo_url
                await new_client.deploy_from_tarball(new_app_name, tarball_url)

            # 4. Scale Worker Dyno
            await new_client.scale_dyno(new_app_name, dyno_type=dyno_type, quantity=1)

            # 5. Update Database Record
            await db.update_app_heroku_name(app_id, new_app_name)
            await db.update_app_status(app_id, "running")

            success_count += 1
            logs.append(f"✅ {display_name} -> `{new_app_name}` (Running)")

            # 6. Notify Bot Owner
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🎉 **Bot Auto-Restored Successfully!**\n\n"
                        f"🤖 **Bot Name:** `{display_name}`\n"
                        f"⚡ **Status:** 🟢 Running 24/7\n\n"
                        f"Your bot has been seamlessly migrated to the new cloud server with all your settings preserved."
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        # Save new Heroku API Key in settings
        await db.set_setting("active_heroku_api_key", new_api_key)
        return success_count, fail_count, logs

recovery_engine = DisasterRecoveryEngine()
