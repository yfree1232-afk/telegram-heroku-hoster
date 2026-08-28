import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from config import config
from core.database import db
from utils.states import AdminStates

router = Router()

@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    await callback.message.edit_text(
        "📢 **Broadcast Message to All Users**\n\n"
        "Send the message you want to broadcast (Markdown formatting supported):",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_msg)
async def msg_receive_broadcast(message: Message, state: FSMContext):
    if not config.is_admin(message.from_user.id):
        return

    users = await db.get_all_users()
    broadcast_text = message.text

    status_msg = await message.reply(f"⏳ Broadcasting to {len(users)} users...")
    success_count = 0
    fail_count = 0

    for u in users:
        try:
            await message.bot.send_message(chat_id=u["user_id"], text=broadcast_text, parse_mode="Markdown")
            success_count += 1
            await asyncio.sleep(0.05) # Prevent flood limit
        except Exception:
            fail_count += 1

    await state.clear()
    await status_msg.edit_text(
        f"✅ **Broadcast Completed!**\n\n"
        f"• Delivered: `{success_count}`\n"
        f"• Failed / Blocked: `{fail_count}`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel")]
        ]),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_credit_user")
async def cb_admin_credit_user(callback: CallbackQuery, state: FSMContext):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    await callback.message.edit_text(
        "➕ **Add Balance to User**\n\n"
        "Enter the Telegram `User ID` to credit funds:",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_user_id_credit)
    await callback.answer()

@router.message(AdminStates.waiting_for_user_id_credit)
async def msg_receive_credit_user_id(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        return await message.reply("❌ Invalid user ID. Please enter numbers only:")
    
    await state.update_data(credit_user_id=int(text))
    await message.reply("💰 **Enter the amount in INR to add to this user's balance:**")
    await state.set_state(AdminStates.waiting_for_credit_amount)

@router.message(AdminStates.waiting_for_credit_amount)
async def msg_receive_credit_amount(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        return await message.reply("❌ Invalid amount. Enter positive number:")

    amount = int(text)
    data = await state.get_data()
    target_user_id = data["credit_user_id"]

    await db.get_or_create_user(target_user_id)
    new_bal = await db.add_balance(target_user_id, amount)
    await state.clear()

    await message.reply(
        f"✅ **Successfully added ₹{amount} to user `{target_user_id}`!**\nNew Balance: `₹{new_bal}`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel")]
        ]),
        parse_mode="Markdown"
    )

    try:
        await message.bot.send_message(
            chat_id=target_user_id,
            text=f"🎁 **Bonus/Manual Credit Received!**\n\nAn admin added `₹{amount}` to your wallet.\nYour current balance is `₹{new_bal}`.",
            parse_mode="Markdown"
        )
    except Exception:
        pass
