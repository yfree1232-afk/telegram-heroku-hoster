from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from config import config
from core.database import db
from utils.keyboards import get_main_keyboard

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await db.get_or_create_user(user.id, user.username, user.first_name)
    is_admin = config.is_admin(user.id)

    text = (
        f"👋 **Welcome, {user.first_name}!**\n\n"
        f"🚀 **Telegram 24/7 Bot Hosting Platform**\n"
        f"Easily deploy and manage your Telegram bots on high-performance cloud servers without needing any coding or server management skills.\n\n"
        f"✨ **Features:**\n"
        f"• ⚡ 24/7 Non-stop Uptime\n"
        f"• 📦 One-Click Deployment (Music Bot, Filter Bot, Custom GitHub)\n"
        f"• 🔄 Start / Stop / Restart Anytime\n"
        f"• 📋 Real-time Live Logs & Error Checking\n"
        f"• ⚙️ Easy Config Vars (Environment) Editor\n\n"
        f"👇 **Choose an option below to get started:**"
    )
    await message.answer(text, reply_markup=get_main_keyboard(is_admin), parse_mode="Markdown")

@router.callback_query(F.data == "back_to_main")
async def cb_back_to_main(callback: CallbackQuery):
    is_admin = config.is_admin(callback.from_user.id)
    text = (
        f"🏠 **Main Menu**\n\n"
        f"Welcome back! Select an option below to manage your bots or wallet."
    )
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(is_admin), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "user_pricing")
async def cb_user_pricing(callback: CallbackQuery):
    text = (
        f"💰 **Pricing & Hosting Plans**\n\n"
        f"• 🤖 **1 Bot Hosting Slot:** ₹{config.MONTHLY_PRICE_INR} / Month (30 Days)\n"
        f"• ⚡ **Uptime:** 24/7 Dedicated Worker Dyno\n"
        f"• 🛡️ **Support:** Full Live Logs & Crash recovery\n\n"
        f"📌 *How it works:*\n"
        f"1. Add balance to your wallet via UPI QR.\n"
        f"2. Click **Deploy New Bot** and provide your GitHub link & Config Vars.\n"
        f"3. Your bot starts immediately and runs 24/7 for 30 days!"
    )
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(config.is_admin(callback.from_user.id)), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "user_support")
async def cb_user_support(callback: CallbackQuery):
    text = (
        f"💬 **Customer Support & Help**\n\n"
        f"Need help deploying or encountering any errors with your bot?\n\n"
        f"• 👤 **Support Admin:** @{config.SUPPORT_USERNAME}\n"
        f"• 📖 **Tip:** Check your bot's **Live Logs** inside the bot dashboard to see why it crashed or what token is missing."
    )
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(config.is_admin(callback.from_user.id)), parse_mode="Markdown")
    await callback.answer()
