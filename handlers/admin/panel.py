from aiogram import Router, F
from aiogram.types import CallbackQuery
from config import config
from core.database import db
from core.heroku import heroku_client
from utils.keyboards import get_admin_keyboard

router = Router()

def is_admin_filter(callback: CallbackQuery) -> bool:
    return config.is_admin(callback.from_user.id)

@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    text = (
        f"👑 **Master Admin Control Panel**\n\n"
        f"Welcome Admin! From here you can manage all user apps, approve payment receipts, check Heroku account status, and control personal apps."
    )
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    users = await db.get_all_users()
    apps = await db.get_all_active_apps()
    running_apps = [a for a in apps if a.get("status") == "running"]

    # Heroku account check
    ok, acc_info = await heroku_client.get_account()
    heroku_email = acc_info.get("email", "Unknown") if ok else "Disconnected/Error"

    text = (
        f"📊 **Platform Analytics & Health**\n\n"
        f"👥 **Total Registered Users:** `{len(users)}`\n"
        f"🤖 **Total Hosted Bots:** `{len(apps)}`\n"
        f"🟢 **Currently Running:** `{len(running_apps)}`\n"
        f"🔴 **Stopped / Expired:** `{len(apps) - len(running_apps)}`\n\n"
        f"☁️ **Heroku Master Account:** `{heroku_email}`\n"
        f"💰 **Monthly Slot Price:** `₹{config.MONTHLY_PRICE_INR}`\n"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")
    await callback.answer()
