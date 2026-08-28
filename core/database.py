import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from config import config

logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self, uri: str = config.MONGO_URI, db_name: str = config.DATABASE_NAME):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        
        # Collections
        self.users = self.db["users"]
        self.apps = self.db["apps"]
        self.payments = self.db["payments"]
        self.templates = self.db["templates"]
        self.settings = self.db["settings"]

    async def init(self):
        """Initialize indexes and default seed data"""
        try:
            # Create indexes
            await self.users.create_index("user_id", unique=True)
            await self.apps.create_index("id", unique=True)
            await self.apps.create_index("heroku_app_name")
            await self.payments.create_index("id", unique=True)
            await self.templates.create_index("id", unique=True)

            # Seed default templates if empty
            count = await self.templates.count_documents({})
            if count == 0:
                default_templates = [
                    {
                        "id": 1,
                        "name": "Telegram Music Bot",
                        "description": "High-quality VC Music Streaming Bot with YouTube/Spotify support.",
                        "repo_url": "https://github.com/AnonymousX1025/AnonXMusic",
                        "required_vars": ["BOT_TOKEN", "API_ID", "API_HASH", "MONGO_DB_URI", "STRING_SESSION", "OWNER_ID"]
                    },
                    {
                        "id": 2,
                        "name": "Auto Filter & File Store Bot",
                        "description": "Channel filter & auto-index telegram file sharing bot.",
                        "repo_url": "https://github.com/EvamariaTG/EvaMaria",
                        "required_vars": ["BOT_TOKEN", "API_ID", "API_HASH", "DATABASE_URI", "DATABASE_NAME", "ADMINS"]
                    },
                    {
                        "id": 3,
                        "name": "Telegram Userbot",
                        "description": "Powerful helper userbot for personal Telegram account automation.",
                        "repo_url": "https://github.com/TeamYukki/YukkiMusicBot",
                        "required_vars": ["BOT_TOKEN", "API_ID", "API_HASH", "MONGO_DB_URI", "STRING_SESSION", "OWNER_ID"]
                    }
                ]
                await self.templates.insert_many(default_templates)
            logger.info("MongoDB initialized successfully.")
        except Exception as e:
            logger.exception(f"Failed to initialize MongoDB: {e}")

    async def _get_next_id(self, collection_name: str) -> int:
        col = self.db[collection_name]
        last_doc = await col.find_one(sort=[("id", -1)])
        return (last_doc["id"] + 1) if last_doc and "id" in last_doc else 1

    # --- User Operations ---
    async def get_or_create_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> Dict[str, Any]:
        user = await self.users.find_one({"user_id": user_id})
        if user:
            await self.users.update_one(
                {"user_id": user_id},
                {"$set": {"username": username, "first_name": first_name}}
            )
            user["username"] = username
            user["first_name"] = first_name
            return user

        new_user = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "balance": 0,
            "is_banned": False,
            "created_at": datetime.utcnow()
        }
        await self.users.insert_one(new_user)
        return new_user

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await self.users.find_one({"user_id": user_id})

    async def add_balance(self, user_id: int, amount: int) -> int:
        await self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": amount}}
        )
        user = await self.users.find_one({"user_id": user_id})
        return user.get("balance", 0) if user else 0

    async def deduct_balance(self, user_id: int, amount: int) -> bool:
        user = await self.users.find_one({"user_id": user_id})
        if not user or user.get("balance", 0) < amount:
            return False
        await self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": -amount}}
        )
        return True

    async def get_all_users(self) -> List[Dict[str, Any]]:
        cursor = self.users.find().sort("created_at", -1)
        return await cursor.to_list(length=None)

    # --- App Operations ---
    async def register_app(
        self,
        user_id: int,
        heroku_app_name: str,
        display_name: str,
        repo_url: Optional[str] = None,
        config_vars: Optional[Dict[str, str]] = None,
        dyno_type: str = "worker",
        duration_days: int = 30,
        is_admin_app: bool = False
    ) -> int:
        app_id = await self._get_next_id("apps")
        expires_at = datetime.utcnow() + timedelta(days=duration_days) if not is_admin_app else None
        
        doc = {
            "id": app_id,
            "user_id": user_id,
            "heroku_app_name": heroku_app_name,
            "display_name": display_name,
            "repo_url": repo_url,
            "config_vars": config_vars or {},
            "dyno_type": dyno_type,
            "status": "running",
            "expires_at": expires_at.isoformat() if expires_at else None,
            "created_at": datetime.utcnow().isoformat(),
            "is_admin_app": bool(is_admin_app)
        }
        await self.apps.insert_one(doc)
        return app_id

    async def get_user_apps(self, user_id: int) -> List[Dict[str, Any]]:
        cursor = self.apps.find({"user_id": user_id}).sort("id", -1)
        return await cursor.to_list(length=None)

    async def get_app_by_name(self, heroku_app_name: str) -> Optional[Dict[str, Any]]:
        return await self.apps.find_one({"heroku_app_name": heroku_app_name})

    async def get_app_by_id(self, app_id: int) -> Optional[Dict[str, Any]]:
        return await self.apps.find_one({"id": app_id})

    async def update_app_status(self, app_id: int, status: str):
        await self.apps.update_one({"id": app_id}, {"$set": {"status": status}})

    async def update_app_config_vars(self, app_id: int, updated_vars: Dict[str, Optional[str]]):
        app = await self.get_app_by_id(app_id)
        if not app:
            return
        current_vars = app.get("config_vars", {})
        for k, v in updated_vars.items():
            if v is None:
                current_vars.pop(k, None)
            else:
                current_vars[k] = v
        await self.apps.update_one({"id": app_id}, {"$set": {"config_vars": current_vars}})

    async def update_app_heroku_name(self, app_id: int, new_heroku_name: str):
        await self.apps.update_one({"id": app_id}, {"$set": {"heroku_app_name": new_heroku_name}})

    async def extend_app_subscription(self, app_id: int, days: int = 30) -> datetime:
        app = await self.get_app_by_id(app_id)
        now = datetime.utcnow()
        if app and app.get("expires_at"):
            try:
                current_exp = datetime.fromisoformat(app["expires_at"])
                new_exp = max(now, current_exp) + timedelta(days=days)
            except Exception:
                new_exp = now + timedelta(days=days)
        else:
            new_exp = now + timedelta(days=days)

        await self.apps.update_one(
            {"id": app_id},
            {"$set": {"expires_at": new_exp.isoformat(), "status": "running"}}
        )
        return new_exp

    async def delete_app_record(self, app_id: int):
        await self.apps.delete_one({"id": app_id})

    async def get_all_active_apps(self) -> List[Dict[str, Any]]:
        cursor = self.apps.find().sort("id", -1)
        return await cursor.to_list(length=None)

    # --- Payment Operations ---
    async def create_payment_request(self, user_id: int, amount: int, utr_number: Optional[str] = None, screenshot_file_id: Optional[str] = None) -> int:
        payment_id = await self._get_next_id("payments")
        doc = {
            "id": payment_id,
            "user_id": user_id,
            "amount": amount,
            "utr_number": utr_number,
            "screenshot_file_id": screenshot_file_id,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "reviewed_by": None,
            "reviewed_at": None
        }
        await self.payments.insert_one(doc)
        return payment_id

    async def get_payment(self, payment_id: int) -> Optional[Dict[str, Any]]:
        return await self.payments.find_one({"id": payment_id})

    async def update_payment_status(self, payment_id: int, status: str, reviewed_by: int) -> bool:
        await self.payments.update_one(
            {"id": payment_id},
            {"$set": {
                "status": status,
                "reviewed_by": reviewed_by,
                "reviewed_at": datetime.utcnow().isoformat()
            }}
        )
        return True

    # --- Template Operations ---
    async def get_templates(self) -> List[Dict[str, Any]]:
        cursor = self.templates.find()
        return await cursor.to_list(length=None)

    async def get_template_by_id(self, template_id: int) -> Optional[Dict[str, Any]]:
        return await self.templates.find_one({"id": template_id})

    # --- Global Dynamic Settings ---
    async def get_setting(self, key: str, default: Any = None) -> Any:
        doc = await self.settings.find_one({"key": key})
        return doc["value"] if doc and "value" in doc else default

    async def set_setting(self, key: str, value: Any):
        await self.settings.update_one(
            {"key": key},
            {"$set": {"value": value, "updated_at": datetime.utcnow().isoformat()}},
            upsert=True
        )

db = MongoDB()
