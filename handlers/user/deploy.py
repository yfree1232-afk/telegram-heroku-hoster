import re
import random
import string
import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from config import config
from core.database import db
from core.heroku import heroku_client
from utils.states import DeployStates
from utils.keyboards import get_template_picker_keyboard
from utils.helpers import parse_config_vars_text, github_repo_to_tarball

router = Router()

def make_safe_heroku_name(name: str) -> str:
    # Lowercase, alphanumeric and hyphens only, between 3-30 chars
    cleaned = re.sub(r'[^a-z0-9-]', '', name.lower().replace(" ", "-"))
    if len(cleaned) < 3:
        cleaned = "bot-host"
    rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{cleaned[:20]}-{rand_suffix}"

@router.callback_query(F.data == "user_deploy_menu")
async def cb_deploy_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    user_data = await db.get_user(user_id)
    balance = user_data.get("balance", 0) if user_data else 0
    is_admin = config.is_admin(user_id)

    if not is_admin and balance < config.MONTHLY_PRICE_INR:
        text = (
            f"⚠️ **Insufficient Balance!**\n\n"
            f"Your current balance is `₹{balance}`.\n"
            f"Deploying a bot requires `₹{config.MONTHLY_PRICE_INR}` for 30 Days 24/7 Hosting.\n\n"
            f"Please recharge your wallet to proceed."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Recharge Wallet", callback_data="user_billing")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
        return

    templates = await db.get_templates()
    text = (
        f"🚀 **Deploy a New Bot**\n\n"
        f"💰 **Hosting Fee:** ₹{config.MONTHLY_PRICE_INR} / 30 Days\n"
        f"⚡ **Uptime:** 24/7 Dedicated Worker\n\n"
        f"Select a pre-configured bot template below or deploy your own custom GitHub repository:"
    )
    await callback.message.edit_text(text, reply_markup=get_template_picker_keyboard(templates), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("deploy_tmpl_"))
async def cb_deploy_template(callback: CallbackQuery, state: FSMContext):
    tmpl_id = int(callback.data.split("_")[2])
    template = await db.get_template_by_id(tmpl_id)
    if not template:
        await callback.answer("Template not found.", show_alert=True)
        return

    await state.update_data(
        template_name=template["name"],
        repo_url=template["repo_url"],
        required_vars=json.loads(template["required_vars"])
    )

    await callback.message.edit_text(
        f"📦 **Template Selected: {template['name']}**\n\n"
        f"📝 **Description:** {template['description']}\n"
        f"🔗 **Repo:** `{template['repo_url']}`\n\n"
        f"👉 **Please enter a name for your bot:** (e.g. `MyMusicBot` or `AlphaBot`)",
        parse_mode="Markdown"
    )
    await state.set_state(DeployStates.waiting_for_app_name)
    await callback.answer()

@router.callback_query(F.data == "deploy_custom_repo")
async def cb_deploy_custom_repo(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔗 **Enter your public GitHub Repository URL:**\n\n"
        "Example:\n`https://github.com/Username/TelegramBot`",
        parse_mode="Markdown"
    )
    await state.set_state(DeployStates.waiting_for_repo_url)
    await callback.answer()

@router.message(DeployStates.waiting_for_repo_url)
async def msg_receive_repo_url(message: Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith("http") or "github.com" not in url:
        await message.reply("❌ Please enter a valid GitHub repository URL (e.g. `https://github.com/user/repo`).")
        return

    await state.update_data(repo_url=url, template_name="Custom Bot", required_vars=[])
    await message.reply(
        "👉 **Now enter a name for your bot:** (e.g. `MyTelegramBot`):",
        parse_mode="Markdown"
    )
    await state.set_state(DeployStates.waiting_for_app_name)

@router.message(DeployStates.waiting_for_app_name)
async def msg_receive_app_name(message: Message, state: FSMContext):
    display_name = message.text.strip()
    if len(display_name) < 2 or len(display_name) > 30:
        await message.reply("❌ Name must be between 2 and 30 characters. Please enter a valid name:")
        return

    data = await state.get_data()
    required_vars = data.get("required_vars", [])
    
    await state.update_data(display_name=display_name)

    sample_vars = ""
    if required_vars:
        sample_vars = "\n".join([f"{var}=your_value_here" for var in required_vars])
    else:
        sample_vars = "BOT_TOKEN=123456:ABC...\nAPI_ID=12345\nAPI_HASH=abcd1234..."

    text = (
        f"⚙️ **Set Environment Variables (Config Vars)**\n\n"
        f"Send all the required configuration variables in `KEY=VALUE` format (one per line):\n\n"
        f"```text\n{sample_vars}\n```\n"
        f"*(You can copy, fill your actual values, and send as a single message)*"
    )
    await message.reply(text, parse_mode="Markdown")
    await state.set_state(DeployStates.waiting_for_config_vars)

@router.message(DeployStates.waiting_for_config_vars)
async def msg_receive_config_vars(message: Message, state: FSMContext):
    raw_vars = message.text.strip()
    parsed_vars = parse_config_vars_text(raw_vars)

    if not parsed_vars:
        await message.reply("❌ No valid environment variables detected. Format should be `KEY=VALUE` (e.g. `BOT_TOKEN=123456:ABC`). Try again:")
        return

    await state.update_data(config_vars=parsed_vars)
    data = await state.get_data()

    vars_preview = "\n".join([f"• `{k}` = `{'*'*8 if len(v)>4 else v}`" for k, v in parsed_vars.items()])

    confirm_text = (
        f"🚀 **Ready to Deploy Bot!**\n\n"
        f"🤖 **Bot Name:** `{data['display_name']}`\n"
        f"📦 **Template:** `{data.get('template_name', 'Custom')}`\n"
        f"🔗 **Repository:** `{data['repo_url']}`\n"
        f"💰 **Cost:** `₹{config.MONTHLY_PRICE_INR}` (30 Days)\n\n"
        f"🔑 **Config Variables:**\n{vars_preview}\n\n"
        f"Click **Confirm & Deploy** below to start building your bot on cloud servers."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Confirm & Deploy Now", callback_data="deploy_trigger_build")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_main")]
    ])
    await message.reply(confirm_text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(DeployStates.confirm_deploy)

@router.callback_query(F.data == "deploy_trigger_build")
async def cb_trigger_deploy(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    is_admin = config.is_admin(user_id)

    # Balance check & deduction
    if not is_admin:
        deducted = await db.deduct_balance(user_id, config.MONTHLY_PRICE_INR)
        if not deducted:
            await callback.answer("Insufficient balance in wallet!", show_alert=True)
            return

    status_msg = await callback.message.edit_text("⏳ **Initializing deployment...** (Creating cloud container)", parse_mode="Markdown")
    
    app_name = make_safe_heroku_name(data["display_name"])
    display_name = data["display_name"]
    repo_url = data["repo_url"]
    config_vars = data.get("config_vars", {})

    # 1. Create Heroku App
    ok, app_res = await heroku_client.create_app(app_name)
    if not ok:
        # Refund if failed
        if not is_admin:
            await db.add_balance(user_id, config.MONTHLY_PRICE_INR)
        await status_msg.edit_text(f"❌ **Deployment Failed at App Creation:**\n`{app_res}`\n\nYour balance was refunded.", parse_mode="Markdown")
        await state.clear()
        return

    # 2. Update Config Vars
    await status_msg.edit_text("⚙️ **Configuring Environment Variables...**", parse_mode="Markdown")
    await heroku_client.update_config_vars(app_name, config_vars)

    # 3. Trigger Build from Tarball
    await status_msg.edit_text("📦 **Building source code from GitHub repository...**", parse_mode="Markdown")
    tarball_url = github_repo_to_tarball(repo_url)
    if not tarball_url:
        tarball_url = repo_url # fallback

    build_ok, build_res = await heroku_client.deploy_from_tarball(app_name, tarball_url)
    
    # 4. Scale Worker Dyno to 1
    await status_msg.edit_text("⚡ **Starting 24/7 worker process...**", parse_mode="Markdown")
    await heroku_client.scale_dyno(app_name, dyno_type="worker", quantity=1)

    # 5. Register in DB
    app_db_id = await db.register_app(
        user_id=user_id,
        heroku_app_name=app_name,
        display_name=display_name,
        repo_url=repo_url,
        dyno_type="worker",
        duration_days=30,
        is_admin_app=is_admin
    )

    await state.clear()
    success_text = (
        f"🎉 **Bot Successfully Deployed & Running 24/7!**\n\n"
        f"🤖 **Bot Name:** `{display_name}`\n"
        f"🏷️ **Heroku App:** `{app_name}`\n"
        f"📅 **Active for:** `30 Days`\n"
        f"⚡ **Status:** 🟢 Running\n\n"
        f"Click **Bot Dashboard** below to view live logs or configure your bot."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Open Bot Dashboard", callback_data=f"app_view_{app_db_id}")],
        [InlineKeyboardButton(text="📋 View Live Logs", callback_data=f"app_logs_{app_db_id}")],
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_to_main")]
    ])
    await status_msg.edit_text(success_text, reply_markup=kb, parse_mode="Markdown")
