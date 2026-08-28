from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import config

def get_main_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🚀 My Bots", callback_data="user_my_bots"),
            InlineKeyboardButton(text="➕ Deploy New Bot", callback_data="user_deploy_menu")
        ],
        [
            InlineKeyboardButton(text="💳 Wallet & Subscription", callback_data="user_billing"),
            InlineKeyboardButton(text="💰 Pricing & Plans", callback_data="user_pricing")
        ],
        [
            InlineKeyboardButton(text="💬 Support & Help", callback_data="user_support")
        ]
    ]
    if is_admin:
        buttons.insert(0, [InlineKeyboardButton(text="👑 Master Admin Panel 👑", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_keyboard(pending_count: int = 0) -> InlineKeyboardMarkup:
    pay_label = f"💳 Pending Payments ({pending_count})" if pending_count > 0 else "💳 Payments Queue"
    buttons = [
        [
            InlineKeyboardButton(text="📊 Platform Analytics", callback_data="admin_stats"),
            InlineKeyboardButton(text=pay_label, callback_data="admin_payments")
        ],
        [
            InlineKeyboardButton(text="🤖 Manage All User Bots", callback_data="admin_all_bots"),
            InlineKeyboardButton(text="⚡ Admin Personal Apps", callback_data="admin_personal_apps")
        ],
        [
            InlineKeyboardButton(text="🔄 Auto-Restore All Bots", callback_data="admin_restore_prompt"),
            InlineKeyboardButton(text="📢 Broadcast Announcement", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="➕ Add Balance to User", callback_data="admin_credit_user"),
            InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_user_apps_keyboard(apps: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    for app in apps:
        status_icon = "🟢" if app.get("status") == "running" else "🔴"
        name = app.get("display_name", app.get("heroku_app_name"))
        buttons.append([
            InlineKeyboardButton(text=f"{status_icon} {name}", callback_data=f"app_view_{app['id']}")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="➕ Deploy New Bot", callback_data="user_deploy_menu"),
        InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_app_detail_keyboard(app_id: int, status: str, is_admin_app: bool = False) -> InlineKeyboardMarkup:
    is_running = (status == "running")
    power_btn = InlineKeyboardButton(text="⏹️ Stop Bot", callback_data=f"app_power_stop_{app_id}") if is_running else InlineKeyboardButton(text="▶️ Start Bot", callback_data=f"app_power_start_{app_id}")
    
    buttons = [
        [
            power_btn,
            InlineKeyboardButton(text="🔄 Restart", callback_data=f"app_restart_{app_id}")
        ],
        [
            InlineKeyboardButton(text="📋 Live Logs", callback_data=f"app_logs_{app_id}"),
            InlineKeyboardButton(text="⚙️ Config Vars", callback_data=f"app_vars_{app_id}")
        ]
    ]

    if not is_admin_app:
        buttons.append([
            InlineKeyboardButton(text="💳 Renew Subscription (+30d)", callback_data=f"app_renew_{app_id}")
        ])

    buttons.append([
        InlineKeyboardButton(text="🗑️ Delete Bot", callback_data=f"app_delete_prompt_{app_id}"),
        InlineKeyboardButton(text="🔙 My Bots", callback_data="user_my_bots")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_config_vars_keyboard(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Add / Update Var", callback_data=f"app_var_add_{app_id}")
        ],
        [
            InlineKeyboardButton(text="🔄 Refresh", callback_data=f"app_vars_{app_id}"),
            InlineKeyboardButton(text="🔙 Back to Bot", callback_data=f"app_view_{app_id}")
        ]
    ])

def get_template_picker_keyboard(templates: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    for tmpl in templates:
        buttons.append([
            InlineKeyboardButton(text=f"📦 {tmpl['name']}", callback_data=f"deploy_tmpl_{tmpl['id']}")
        ])
    buttons.append([
        InlineKeyboardButton(text="🔗 Custom GitHub Repo Link", callback_data="deploy_custom_repo")
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Cancel", callback_data="back_to_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_approval_keyboard(payment_id: int, user_id: int, amount: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✅ Approve ₹{amount}", callback_data=f"pay_approve_{payment_id}_{user_id}_{amount}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"pay_reject_{payment_id}_{user_id}")
        ]
    ])

def get_renew_keyboard(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"💳 Renew with Wallet Balance (₹{config.MONTHLY_PRICE_INR})", callback_data=f"app_renew_confirm_{app_id}")
        ],
        [
            InlineKeyboardButton(text="💰 Recharge Wallet", callback_data="user_billing"),
            InlineKeyboardButton(text="🔙 My Bots", callback_data="user_my_bots")
        ]
    ])

def get_confirm_delete_keyboard(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚠️ Yes, Permanently Delete", callback_data=f"app_delete_confirm_{app_id}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"app_view_{app_id}")
        ]
    ])
