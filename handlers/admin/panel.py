from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from config import config
from core.database import db
from core.heroku import heroku_client, HerokuAPI
from core.recovery import recovery_engine
from utils.keyboards import get_admin_keyboard
from utils.states import AdminStates

router = Router()

@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    text = (
        f"👑 **Master Admin Control Panel**\n\n"
        f"Welcome Admin! From here you can manage all user apps, approve payment receipts, check Heroku account status, auto-restore bots to a new account, and control personal apps."
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
        f"📊 **Platform Analytics & Health (MongoDB)**\n\n"
        f"👥 **Total Registered Users:** `{len(users)}`\n"
        f"🤖 **Total Hosted Bots:** `{len(apps)}`\n"
        f"🟢 **Currently Running:** `{len(running_apps)}`\n"
        f"🔴 **Stopped / Expired:** `{len(apps) - len(running_apps)}`\n\n"
        f"☁️ **Heroku Master Account:** `{heroku_email}`\n"
        f"🍃 **MongoDB Database:** `Connected & Ultra-Secure`\n"
        f"💰 **Monthly Slot Price:** `₹{config.MONTHLY_PRICE_INR}`\n"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")
    await callback.answer()

# --- Auto-Restore / Disaster Recovery ---
@router.callback_query(F.data == "admin_restore_prompt")
async def cb_admin_restore_prompt(callback: CallbackQuery, state: FSMContext):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    all_apps = await db.get_all_active_apps()
    text = (
        f"🔄 **Disaster Recovery & Heroku Account Auto-Migration**\n\n"
        f"📦 **Saved Bots in MongoDB:** `{len(all_apps)}`\n\n"
        f"If your previous Heroku account was banned or suspended, you can enter a **NEW Heroku API Key** below.\n\n"
        f"The engine will automatically:\n"
        f"1. Create new apps on the new Heroku account.\n"
        f"2. Restore all Config Vars for every user bot.\n"
        f"3. Rebuild and deploy from GitHub repos.\n"
        f"4. Scale worker dynos to 24/7.\n"
        f"5. Notify all users that their bots are back online!\n\n"
        f"👉 **Send the NEW Heroku API Key now:**"
    )
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_panel")]
    ])
    await callback.message.edit_text(text, reply_markup=cancel_kb, parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_restore_key)
    await callback.answer()

@router.message(AdminStates.waiting_for_restore_key)
async def msg_receive_restore_key(message: Message, state: FSMContext):
    if not config.is_admin(message.from_user.id):
        return

    new_key = message.text.strip()
    status_msg = await message.reply("⏳ **Validating new Heroku API Key & starting automatic migration...**")

    success, fail, logs = await recovery_engine.restore_all_bots(new_key, message.bot)
    await state.clear()

    log_summary = "\n".join(logs[:15]) if logs else "No active bots found to restore."

    final_text = (
        f"🎉 **Auto-Restore & Migration Complete!**\n\n"
        f"• ✅ **Successfully Restored:** `{success}`\n"
        f"• ❌ **Failed:** `{fail}`\n\n"
        f"**Migration Logs:**\n{log_summary}"
    )
    await status_msg.edit_text(
        final_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel")]
        ]),
        parse_mode="Markdown"
    )
