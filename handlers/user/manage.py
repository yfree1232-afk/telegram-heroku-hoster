import io
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from config import config
from core.database import db
from core.heroku import heroku_client
from utils.keyboards import get_app_detail_keyboard, get_config_vars_keyboard, get_confirm_delete_keyboard, get_renew_keyboard
from utils.states import ConfigVarStates
from utils.helpers import parse_config_vars_text, format_status_badge

router = Router()

@router.callback_query(F.data.startswith("app_power_start_"))
async def cb_power_start(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[3])
    app = await db.get_app_by_id(app_id)
    if not app:
        return await callback.answer("App not found.", show_alert=True)

    await callback.answer("⏳ Starting bot dyno...", show_alert=False)
    ok, res = await heroku_client.scale_dyno(app["heroku_app_name"], dyno_type=app.get("dyno_type", "worker"), quantity=1)
    if ok:
        await db.update_app_status(app_id, "running")
        await callback.message.edit_reply_markup(reply_markup=get_app_detail_keyboard(app_id, "running", bool(app.get("is_admin_app"))))
        await callback.answer("✅ Bot started successfully!", show_alert=True)
    else:
        await callback.answer(f"❌ Failed to start: {res}", show_alert=True)

@router.callback_query(F.data.startswith("app_power_stop_"))
async def cb_power_stop(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[3])
    app = await db.get_app_by_id(app_id)
    if not app:
        return await callback.answer("App not found.", show_alert=True)

    await callback.answer("⏳ Stopping bot dyno...", show_alert=False)
    ok, res = await heroku_client.scale_dyno(app["heroku_app_name"], dyno_type=app.get("dyno_type", "worker"), quantity=0)
    if ok:
        await db.update_app_status(app_id, "stopped")
        await callback.message.edit_reply_markup(reply_markup=get_app_detail_keyboard(app_id, "stopped", bool(app.get("is_admin_app"))))
        await callback.answer("⏹️ Bot stopped.", show_alert=True)
    else:
        await callback.answer(f"❌ Failed to stop: {res}", show_alert=True)

@router.callback_query(F.data.startswith("app_restart_"))
async def cb_restart(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[2])
    app = await db.get_app_by_id(app_id)
    if not app:
        return await callback.answer("App not found.", show_alert=True)

    await callback.answer("⏳ Restarting dynos...", show_alert=False)
    ok, res = await heroku_client.restart_app(app["heroku_app_name"])
    if ok:
        await callback.answer("🔄 Bot restarted successfully!", show_alert=True)
    else:
        await callback.answer(f"❌ Restart failed: {res}", show_alert=True)

@router.callback_query(F.data.startswith("app_logs_"))
async def cb_logs(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[2])
    app = await db.get_app_by_id(app_id)
    if not app:
        return await callback.answer("App not found.", show_alert=True)

    await callback.answer("⏳ Fetching real-time logs...", show_alert=False)
    ok, logs = await heroku_client.get_recent_logs(app["heroku_app_name"], lines=100)

    if not ok:
        await callback.message.answer(f"❌ **Failed to retrieve logs:**\n`{logs}`", parse_mode="Markdown")
        return

    if len(logs) < 3500:
        text = f"📋 **Live Logs ({app['display_name']}):**\n\n```text\n{logs}\n```"
        await callback.message.answer(text, parse_mode="Markdown")
    else:
        file_bytes = logs.encode("utf-8")
        doc = BufferedInputFile(file_bytes, filename=f"logs_{app['heroku_app_name']}.txt")
        await callback.message.answer_document(doc, caption=f"📋 **Full Logs for {app['display_name']}**")

@router.callback_query(F.data.startswith("app_vars_"))
async def cb_config_vars(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[2])
    app = await db.get_app_by_id(app_id)
    if not app:
        return await callback.answer("App not found.", show_alert=True)

    ok, vars_dict = await heroku_client.get_config_vars(app["heroku_app_name"])
    if not ok:
        return await callback.answer(f"Error fetching vars: {vars_dict}", show_alert=True)

    if not vars_dict:
        vars_text = "_No environment variables configured._"
    else:
        vars_lines = []
        for k, v in vars_dict.items():
            # Mask sensitive values slightly for security
            v_str = str(v)
            masked = v_str[:3] + ("*" * 6) + v_str[-2:] if len(v_str) > 8 else "****"
            vars_lines.append(f"• `{k}` = `{masked}`")
        vars_text = "\n".join(vars_lines)

    text = (
        f"⚙️ **Environment Variables (Config Vars)**\n"
        f"🤖 **Bot:** `{app['display_name']}`\n\n"
        f"{vars_text}\n\n"
        f"👇 Click below to add or update variables:"
    )
    await callback.message.edit_text(text, reply_markup=get_config_vars_keyboard(app_id), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("app_var_add_"))
async def cb_add_var_prompt(callback: CallbackQuery, state: FSMContext):
    app_id = int(callback.data.split("_")[3])
    await state.update_data(target_app_id=app_id)
    await state.set_state(ConfigVarStates.waiting_for_var_input)

    text = (
        "✍️ **Send the variable(s) you want to add or update:**\n\n"
        "Format (one per line):\n"
        "```text\n"
        "BOT_TOKEN=123456:ABC-DEF\n"
        "CUSTOM_VAR=my_new_value\n"
        "```\n"
        "*(Your bot will automatically restart with the new values)*"
    )
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()

@router.message(ConfigVarStates.waiting_for_var_input)
async def msg_receive_var_update(message: Message, state: FSMContext):
    data = await state.get_data()
    app_id = data.get("target_app_id")
    app = await db.get_app_by_id(app_id)

    if not app:
        await state.clear()
        return await message.reply("❌ App not found.")

    parsed = parse_config_vars_text(message.text)
    if not parsed:
        return await message.reply("❌ Invalid format. Please provide in `KEY=VALUE` format.")

    ok, res = await heroku_client.update_config_vars(app["heroku_app_name"], parsed)
    await state.clear()

    if ok:
        await message.reply(
            f"✅ **Variables updated successfully!**\nUpdated `{len(parsed)}` key(s). The bot is restarting with the new configuration.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🤖 Back to Bot Dashboard", callback_data=f"app_view_{app_id}")]
            ]),
            parse_mode="Markdown"
        )
    else:
        await message.reply(f"❌ Failed to update variables: {res}")

@router.callback_query(F.data.startswith("app_renew_"))
async def cb_renew_prompt(callback: CallbackQuery):
    if "confirm" in callback.data:
        app_id = int(callback.data.split("_")[3])
        user_id = callback.from_user.id
        deducted = await db.deduct_balance(user_id, config.MONTHLY_PRICE_INR)
        if not deducted:
            return await callback.answer("Insufficient balance! Please recharge wallet.", show_alert=True)

        app = await db.get_app_by_id(app_id)
        new_exp = await db.extend_app_subscription(app_id, days=30)
        # Ensure dyno is turned on
        await heroku_client.scale_dyno(app["heroku_app_name"], dyno_type=app.get("dyno_type", "worker"), quantity=1)

        await callback.message.edit_text(
            f"🎉 **Subscription Renewed!**\n\n"
            f"🤖 **Bot:** `{app['display_name']}`\n"
            f"📅 **New Expiry Date:** `{new_exp.strftime('%d-%m-%Y')}`\n"
            f"⚡ **Status:** 🟢 Running 24/7",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🤖 Bot Dashboard", callback_data=f"app_view_{app_id}")]
            ]),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    app_id = int(callback.data.split("_")[2])
    text = (
        f"💳 **Renew 24/7 Hosting Plan**\n\n"
        f"• **Extension:** +30 Days\n"
        f"• **Price:** ₹{config.MONTHLY_PRICE_INR}\n\n"
        f"Confirm renewal from your wallet balance?"
    )
    await callback.message.edit_text(text, reply_markup=get_renew_keyboard(app_id), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("app_delete_prompt_"))
async def cb_delete_prompt(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[3])
    text = (
        "⚠️ **Are you sure you want to permanently delete this bot?**\n\n"
        "This will permanently delete the app container and all its configuration from Heroku cloud servers. This action cannot be undone!"
    )
    await callback.message.edit_text(text, reply_markup=get_confirm_delete_keyboard(app_id), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("app_delete_confirm_"))
async def cb_delete_confirm(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[3])
    app = await db.get_app_by_id(app_id)
    if not app:
        return await callback.answer("App not found.", show_alert=True)

    await callback.answer("⏳ Deleting from Heroku...", show_alert=False)
    await heroku_client.delete_app(app["heroku_app_name"])
    await db.delete_app_record(app_id)

    await callback.message.edit_text(
        f"🗑️ **Bot '{app['display_name']}' has been permanently deleted.**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 My Bots", callback_data="user_my_bots")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_to_main")]
        ]),
        parse_mode="Markdown"
    )
