from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery
from config import config
from core.database import db
from core.heroku import heroku_client
from utils.keyboards import get_user_apps_keyboard, get_app_detail_keyboard
from utils.helpers import format_status_badge

router = Router()

@router.callback_query(F.data == "user_my_bots")
async def cb_my_bots(callback: CallbackQuery):
    user_id = callback.from_user.id
    apps = await db.get_user_apps(user_id)

    if not apps:
        text = (
            "🤖 **You don't have any hosted bots yet!**\n\n"
            "Deploy your first bot in less than 2 minutes using our pre-built templates or any custom GitHub repository."
        )
    else:
        text = f"🤖 **Your Hosted Bots ({len(apps)}):**\n\nClick on any bot below to manage power, view live logs, edit environment variables, or renew subscription."

    await callback.message.edit_text(text, reply_markup=get_user_apps_keyboard(apps), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("app_view_"))
async def cb_app_view(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[2])
    app = await db.get_app_by_id(app_id)
    user_id = callback.from_user.id

    if not app or (app["user_id"] != user_id and not config.is_admin(user_id)):
        await callback.answer("App not found or access denied.", show_alert=True)
        return

    # Check live status from Heroku
    ok, dynos = await heroku_client.get_dynos(app["heroku_app_name"])
    current_status = app["status"]
    if ok and isinstance(dynos, list):
        if len(dynos) > 0 and dynos[0].get("state") == "up":
            current_status = "running"
        elif len(dynos) == 0:
            current_status = "stopped"
        else:
            current_status = dynos[0].get("state", "unknown")
        await db.update_app_status(app_id, current_status)

    status_str = format_status_badge(current_status)
    
    expiry_str = "Permanent (Admin)"
    if app.get("expires_at"):
        try:
            exp_date = datetime.fromisoformat(app["expires_at"])
            remaining = exp_date - datetime.utcnow()
            days_left = max(0, remaining.days)
            expiry_str = f"{exp_date.strftime('%d-%m-%Y')} ({days_left} days left)"
        except Exception:
            expiry_str = str(app["expires_at"])

    text = (
        f"🤖 **Bot Dashboard: {app['display_name']}**\n\n"
        f"🏷️ **App Name:** `{app['heroku_app_name']}`\n"
        f"⚡ **Status:** {status_str}\n"
        f"📅 **Subscription:** `{expiry_str}`\n"
        f"🔗 **Repository:** `{app.get('repo_url') or 'Custom Deploy'}`\n\n"
        f"⚙️ *Use the buttons below to control your bot:*"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_app_detail_keyboard(app_id, current_status, bool(app.get("is_admin_app"))),
        parse_mode="Markdown"
    )
    await callback.answer()
