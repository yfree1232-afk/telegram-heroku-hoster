from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import config
from core.database import db

router = Router()

@router.callback_query(F.data.startswith("pay_approve_"))
async def cb_pay_approve(callback: CallbackQuery):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    parts = callback.data.split("_")
    payment_id = int(parts[2])
    target_user_id = int(parts[3])
    amount = int(parts[4])

    # Update payment record
    await db.update_payment_status(payment_id, "approved", callback.from_user.id)
    # Add balance to user
    new_balance = await db.add_balance(target_user_id, amount)

    # Edit admin message
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Approved ₹{amount} by {callback.from_user.first_name}", callback_data="none")]
    ]))
    await callback.answer(f"✅ Approved ₹{amount} for user {target_user_id}", show_alert=True)

    # Notify User
    try:
        user_notify_text = (
            f"🎉 **Payment Approved!**\n\n"
            f"💰 **Amount Credited:** `₹{amount}`\n"
            f"💳 **New Wallet Balance:** `₹{new_balance}`\n\n"
            f"You can now deploy new bots or renew existing subscriptions."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Deploy New Bot", callback_data="user_deploy_menu")],
            [InlineKeyboardButton(text="💳 View Wallet", callback_data="user_billing")]
        ])
        await callback.bot.send_message(chat_id=target_user_id, text=user_notify_text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass

@router.callback_query(F.data.startswith("pay_reject_"))
async def cb_pay_reject(callback: CallbackQuery):
    if not config.is_admin(callback.from_user.id):
        return await callback.answer("Access denied.", show_alert=True)

    parts = callback.data.split("_")
    payment_id = int(parts[2])
    target_user_id = int(parts[3])

    await db.update_payment_status(payment_id, "rejected", callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"❌ Rejected by {callback.from_user.first_name}", callback_data="none")]
    ]))
    await callback.answer(f"❌ Payment #{payment_id} rejected.", show_alert=True)

    # Notify User
    try:
        await callback.bot.send_message(
            chat_id=target_user_id,
            text=(
                "❌ **Your payment verification was rejected.**\n\n"
                "Possible reasons:\n"
                "• Invalid or already used UTR transaction reference.\n"
                "• Screenshot could not be verified.\n\n"
                f"If you believe this was an error, please contact @{config.SUPPORT_USERNAME}."
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass
