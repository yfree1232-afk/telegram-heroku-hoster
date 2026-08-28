from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from config import config
from core.database import db
from utils.helpers import generate_upi_qr
from utils.states import BillingStates
from utils.keyboards import get_payment_approval_keyboard

router = Router()

@router.callback_query(F.data == "user_billing")
async def cb_user_billing(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    user_data = await db.get_user(user_id)
    balance = user_data.get("balance", 0) if user_data else 0

    text = (
        f"💳 **Wallet & Subscription Balance**\n\n"
        f"💰 **Current Balance:** `₹{balance}`\n"
        f"🏷️ **1 Bot Hosting Rate:** `₹{config.MONTHLY_PRICE_INR} / 30 Days`\n\n"
        f"You can add funds to your wallet anytime via UPI (GPay, PhonePe, Paytm, BHIM)."
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"➕ Add ₹{config.MONTHLY_PRICE_INR} (1 Slot)", callback_data=f"pay_amount_{config.MONTHLY_PRICE_INR}"),
            InlineKeyboardButton(text=f"➕ Add ₹{config.MONTHLY_PRICE_INR * 2} (2 Slots)", callback_data=f"pay_amount_{config.MONTHLY_PRICE_INR * 2}")
        ],
        [
            InlineKeyboardButton(text="➕ Custom Amount", callback_data="pay_custom_amount")
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")
        ]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("pay_amount_"))
async def cb_pay_amount(callback: CallbackQuery, state: FSMContext):
    amount = int(callback.data.split("_")[2])
    await process_payment_screen(callback.message, callback.from_user.id, amount, state)
    await callback.answer()

@router.callback_query(F.data == "pay_custom_amount")
async def cb_pay_custom_amount(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✍️ **Enter the amount in INR you wish to add to your wallet:**\n(Minimum: ₹50)",
        parse_mode="Markdown"
    )
    await state.set_state(BillingStates.waiting_for_amount)
    await callback.answer()

@router.message(BillingStates.waiting_for_amount)
async def msg_receive_custom_amount(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or int(text) < 50:
        await message.reply("❌ Invalid amount. Please enter a valid number (minimum ₹50):")
        return
    amount = int(text)
    await process_payment_screen(message, message.from_user.id, amount, state)

async def process_payment_screen(message: Message, user_id: int, amount: int, state: FSMContext):
    await state.update_data(payment_amount=amount)
    await state.set_state(BillingStates.waiting_for_payment_proof)

    # Generate QR
    qr_buf = generate_upi_qr(config.UPI_ID, config.UPI_PAYEE_NAME, amount)
    photo = BufferedInputFile(qr_buf.getvalue(), filename="upi_qr.png")

    caption = (
        f"💳 **Payment Request: ₹{amount}**\n\n"
        f"1️⃣ **Scan QR Code** above using any UPI App (GPay / PhonePe / Paytm / BHIM) OR transfer to:\n"
        f"👉 UPI ID: `{config.UPI_ID}`\n"
        f"👉 Name: `{config.UPI_PAYEE_NAME}`\n\n"
        f"2️⃣ After successful payment, **reply with your 12-Digit UTR Number or send a Screenshot** of the receipt.\n\n"
        f"⏳ *Your balance will be credited automatically upon verification.*"
    )
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel Payment", callback_data="user_billing")]
    ])
    await message.answer_photo(photo=photo, caption=caption, reply_markup=cancel_kb, parse_mode="Markdown")

@router.message(BillingStates.waiting_for_payment_proof)
async def msg_receive_payment_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("payment_amount", config.MONTHLY_PRICE_INR)
    user_id = message.from_user.id

    utr_number = None
    photo_file_id = None

    if message.photo:
        photo_file_id = message.photo[-1].file_id
        if message.caption:
            utr_number = message.caption.strip()
    elif message.text:
        utr_number = message.text.strip()
    else:
        await message.reply("❌ Please send a valid screenshot or UTR number text.")
        return

    payment_id = await db.create_payment_request(
        user_id=user_id,
        amount=amount,
        utr_number=utr_number,
        screenshot_file_id=photo_file_id
    )

    await state.clear()
    await message.reply(
        "✅ **Payment proof submitted successfully!**\n\n"
        "Our admin is verifying your transaction. Once approved, your wallet balance will be updated instantly.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Back to Menu", callback_data="back_to_main")]
        ]),
        parse_mode="Markdown"
    )

    # Notify Admins
    admin_text = (
        f"🔔 **New Payment Received!**\n\n"
        f"👤 **User:** `{message.from_user.full_name}` (`{user_id}`)\n"
        f"💰 **Amount:** `₹{amount}`\n"
        f"🔢 **UTR / Note:** `{utr_number or 'N/A'}`\n"
        f"🆔 **Payment ID:** `#{payment_id}`"
    )
    kb = get_payment_approval_keyboard(payment_id, user_id, amount)

    for admin_id in config.ADMIN_IDS:
        try:
            if photo_file_id:
                await message.bot.send_photo(chat_id=admin_id, photo=photo_file_id, caption=admin_text, reply_markup=kb, parse_mode="Markdown")
            else:
                await message.bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
