from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import config
from core.database import db
from core.heroku import heroku_client

router = Router()

@router.callback_query(F.data == "admin_all_bots")
async def cb_admin_all_bots(callback: CallbackQuery):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    apps = await db.get_all_active_apps()
    if not apps:
        text = "🤖 **No user bots deployed yet.**"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel")]])
    else:
        text = f"🤖 **All Hosted Bots Across Platform ({len(apps)}):**\n\nSelect a bot to view full details, stop, restart, or delete:"
        buttons = []
        for a in apps:
            status_icon = "🟢" if a.get("status") == "running" else "🔴"
            user_lbl = f"(User: {a['user_id']})"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status_icon} {a['display_name']} {user_lbl}",
                    callback_data=f"app_view_{a['id']}"
                )
            ])
        buttons.append([InlineKeyboardButton(text="🔙 Back to Admin Panel", callback_data="admin_panel")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "admin_personal_apps")
async def cb_admin_personal_apps(callback: CallbackQuery):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    await callback.answer("Fetching apps from Heroku account...", show_alert=False)
    ok, heroku_apps = await heroku_client.list_apps()

    if not ok or not isinstance(heroku_apps, list):
        text = f"❌ **Failed to list Heroku apps:**\n`{heroku_apps}`"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel")]])
    else:
        text = f"👑 **All Apps in Heroku Account ({len(heroku_apps)}):**\n\nThese are directly fetched from your Heroku API key."
        buttons = []
        for app in heroku_apps[:25]: # cap at 25 for telegram button limit
            app_name = app.get("name")
            buttons.append([
                InlineKeyboardButton(text=f"⚡ {app_name}", callback_data=f"admin_direct_app_{app_name}")
            ])
        buttons.append([InlineKeyboardButton(text="🔙 Back to Admin Panel", callback_data="admin_panel")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_direct_app_"))
async def cb_admin_direct_app(callback: CallbackQuery):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    app_name = callback.data.split("admin_direct_app_")[1]
    ok, dynos = await heroku_client.get_dynos(app_name)
    status_text = "Stopped (0 Dynos)"
    if ok and isinstance(dynos, list) and len(dynos) > 0:
        status_text = f"Running ({len(dynos)} Dyno: {dynos[0].get('state')})"

    text = (
        f"👑 **Heroku Direct App: {app_name}**\n\n"
        f"⚡ **Dyno Status:** `{status_text}`\n"
        f"🏷️ **App Name:** `{app_name}`\n\n"
        f"Choose an action:"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="▶️ Start (1 Dyno)", callback_data=f"admin_dyno_scale_{app_name}_1"),
            InlineKeyboardButton(text="⏹️ Stop (0 Dynos)", callback_data=f"admin_dyno_scale_{app_name}_0")
        ],
        [
            InlineKeyboardButton(text="🔄 Restart App", callback_data=f"admin_dyno_restart_{app_name}"),
            InlineKeyboardButton(text="📋 Get Logs", callback_data=f"admin_dyno_logs_{app_name}")
        ],
        [
            InlineKeyboardButton(text="🔙 Back to Personal Apps", callback_data="admin_personal_apps")
        ]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_dyno_scale_"))
async def cb_admin_dyno_scale(callback: CallbackQuery):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    parts = callback.data.split("_")
    qty = int(parts[-1])
    app_name = "_".join(parts[3:-1])

    ok, res = await heroku_client.scale_dyno(app_name, dyno_type="worker", quantity=qty)
    if ok:
        await callback.answer(f"✅ Scaled {app_name} to {qty} worker(s)!", show_alert=True)
    else:
        # Try scaling web dyno if worker failed
        ok2, res2 = await heroku_client.scale_dyno(app_name, dyno_type="web", quantity=qty)
        if ok2:
            await callback.answer(f"✅ Scaled {app_name} web to {qty} dyno(s)!", show_alert=True)
        else:
            await callback.answer(f"❌ Failed: {res}", show_alert=True)

@router.callback_query(F.data.startswith("admin_dyno_restart_"))
async def cb_admin_dyno_restart(callback: CallbackQuery):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    app_name = callback.data.replace("admin_dyno_restart_", "")
    ok, res = await heroku_client.restart_app(app_name)
    if ok:
        await callback.answer(f"🔄 Restarted {app_name}!", show_alert=True)
    else:
        await callback.answer(f"❌ Error: {res}", show_alert=True)

@router.callback_query(F.data.startswith("admin_dyno_logs_"))
async def cb_admin_dyno_logs(callback: CallbackQuery):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    app_name = callback.data.replace("admin_dyno_logs_", "")
    await callback.answer("Fetching logs...", show_alert=False)
    ok, logs = await heroku_client.get_recent_logs(app_name, lines=100)
    if not ok:
        return await callback.message.answer(f"❌ Failed to fetch logs: {logs}")
    
    if len(logs) < 3500:
        await callback.message.answer(f"📋 **Logs for {app_name}:**\n\n```text\n{logs}\n```", parse_mode="Markdown")
    else:
        from aiogram.types import BufferedInputFile
        doc = BufferedInputFile(logs.encode("utf-8"), filename=f"logs_{app_name}.txt")
        await callback.message.answer_document(doc, caption=f"📋 **Logs for {app_name}**")
