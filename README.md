# 🚀 Telegram Heroku Bot Hoster & Subscription Platform

A complete, production-ready Telegram Bot management & paid hosting system powered by the **Heroku Platform API v3**.

Deploy, manage, and monetize Telegram bot hosting with automated UPI payments, live log streaming, power controls (start/stop/restart), environment variables editing, and subscription auto-expiry handling.

---

## ✨ Features

### 👤 User Panel (Clients)
- **⚡ 24/7 Bot Deployment**: Deploy from popular templates (Music Bot, Auto Filter Bot, Userbot) or custom GitHub URLs in under 2 minutes.
- **🎮 Full Remote Controls**:
  - **Power**: Turn On (`worker=1`), Turn Off (`worker=0`), Restart.
  - **Live Logs**: Stream real-time logs or download complete `.txt` logs.
  - **Config Vars**: Add, update, or remove Environment Variables directly in chat.
  - **Auto Restart**: Changes to config vars automatically trigger app reload.
- **💳 Wallet & Subscriptions**:
  - Pay via dynamic in-chat UPI QR code.
  - Submit UTR / Screenshot receipts for instant approval.
  - Transparent 30-day billing per bot slot with renewal reminders.

### 👑 Master Admin Panel
- **📊 Real-time Analytics**: Total registered users, active/expired bots, and Heroku account quota.
- **⚡ Direct Heroku App Access**: Inspect, power toggle, and fetch logs for ALL personal and client apps on your Heroku account.
- **💳 Payment Verification Queue**: One-click **[Approve]** and **[Reject]** buttons for UPI transactions with instant wallet top-ups.
- **🎁 Manual Credit**: Instantly grant free hosting credits/balance to any user.
- **📢 Broadcast System**: Send announcements to all registered platform users.
- **⏰ Automated Expiry Scheduler**: Background daemon that warns users before expiry and automatically scales dynos to 0 upon plan expiration.

---

## 🛠️ Setup Guide

### 1. Requirements
- Python 3.10+
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- A Heroku Account & API Key from [Heroku Account Settings](https://dashboard.heroku.com/account)
- Your Telegram User ID from [@userinfobot](https://t.me/userinfobot)
- A UPI ID (GPay / PhonePe / Paytm / BHIM)

---

### 2. Installation

1. **Clone or Navigate to the project directory:**
   ```bash
   cd telegram_heroku_hoster
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env   # On Windows
   # or
   cp .env.example .env     # On Linux/macOS
   ```

   Fill in your `.env` credentials:
   ```env
   BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuvWXyz
   ADMIN_IDS=123456789,987654321

   HEROKU_API_KEY=your-heroku-api-key-here
   HEROKU_EMAIL=your-email@example.com

   MONTHLY_PRICE_INR=100
   UPI_ID=yourname@upi
   UPI_PAYEE_NAME=Bot Hosting Service

   SUPPORT_USERNAME=YourTelegramUsername
   DATABASE_PATH=bot_hoster.db
   ```

---

### 3. Run the Bot

```bash
python main.py
```

---

## 📁 Project Structure

```
telegram_heroku_hoster/
├── config.py                 # Configuration loader & validator
├── main.py                   # Dispatcher & application entry point
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
│
├── core/
│   ├── database.py           # Async SQLite database models & queries
│   ├── heroku.py             # Heroku Platform API v3 async wrapper
│   └── scheduler.py          # Background auto-expiry & reminder worker
│
├── handlers/
│   ├── common.py             # /start, /help, pricing & support
│   ├── user/
│   │   ├── dashboard.py      # My bots list & app overview
│   │   ├── billing.py        # Wallet recharge & UPI QR workflow
│   │   ├── deploy.py         # 1-click bot deployment wizard
│   │   └── manage.py         # Start/Stop/Restart, Logs, Config Vars
│   └── admin/
│       ├── panel.py          # Master admin dashboard & analytics
│       ├── payments.py       # Payment approval/rejection handling
│       ├── manage_all.py     # All bots & personal apps controller
│       └── broadcast.py      # Global broadcast & user wallet credits
│
└── utils/
    ├── helpers.py            # UPI QR generator & helper parsers
    ├── keyboards.py          # Interactive inline keyboard layouts
    └── states.py             # Aiogram Finite State Machine (FSM)
```

---

## 🔒 Security Best Practices
- **Never share your `HEROKU_API_KEY` or `BOT_TOKEN` publicly.**
- The bot automatically protects Heroku credentials and only exposes safe controls to regular users.
- Regular users can only access apps associated with their own Telegram User ID.
