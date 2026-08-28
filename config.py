import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # Parse comma-separated Admin IDs
    _admin_ids_raw = os.getenv("ADMIN_IDS", "")
    ADMIN_IDS: List[int] = [
        int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()
    ]
    
    # Heroku Configuration
    HEROKU_API_KEY: str = os.getenv("HEROKU_API_KEY", "")
    HEROKU_EMAIL: str = os.getenv("HEROKU_EMAIL", "")
    HEROKU_BASE_URL: str = "https://api.heroku.com"
    
    # Pricing & UPI details
    MONTHLY_PRICE_INR: int = int(os.getenv("MONTHLY_PRICE_INR", "100"))
    UPI_ID: str = os.getenv("UPI_ID", "your_upi_id@bank")
    UPI_PAYEE_NAME: str = os.getenv("UPI_PAYEE_NAME", "Bot Hoster")
    
    # Support
    SUPPORT_USERNAME: str = os.getenv("SUPPORT_USERNAME", "admin")
    
    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bot_hoster.db")
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        return user_id in cls.ADMIN_IDS

config = Config()
