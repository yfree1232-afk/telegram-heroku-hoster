import aiosqlite
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from config import config

class Database:
    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path

    async def init(self):
        """Initialize database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    balance INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS apps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    heroku_app_name TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    repo_url TEXT,
                    dyno_type TEXT DEFAULT 'worker',
                    status TEXT DEFAULT 'stopped',
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_admin_app INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    utr_number TEXT,
                    screenshot_file_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_by INTEGER,
                    reviewed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    repo_url TEXT NOT NULL,
                    required_vars TEXT DEFAULT '[]'
                )
            """)
            await db.commit()

            # Seed default templates if empty
            async with db.execute("SELECT COUNT(*) FROM templates") as cursor:
                count = (await cursor.fetchone())[0]
                if count == 0:
                    default_templates = [
                        (
                            "Telegram Music Bot",
                            "High-quality VC Music Streaming Bot with YouTube/Spotify support.",
                            "https://github.com/AnonymousX1025/AnonXMusic",
                            json.dumps(["BOT_TOKEN", "API_ID", "API_HASH", "MONGO_DB_URI", "STRING_SESSION", "OWNER_ID"])
                        ),
                        (
                            "Auto Filter & File Store Bot",
                            "Channel filter & auto-index telegram file sharing bot.",
                            "https://github.com/EvamariaTG/EvaMaria",
                            json.dumps(["BOT_TOKEN", "API_ID", "API_HASH", "DATABASE_URI", "DATABASE_NAME", "ADMINS"])
                        ),
                        (
                            "Telegram Userbot",
                            "Powerful helper userbot for personal Telegram account automation.",
                            "https://github.com/TeamYukki/YukkiMusicBot",
                            json.dumps(["BOT_TOKEN", "API_ID", "API_HASH", "MONGO_DB_URI", "STRING_SESSION", "OWNER_ID"])
                        )
                    ]
                    await db.executemany(
                        "INSERT INTO templates (name, description, repo_url, required_vars) VALUES (?, ?, ?, ?)",
                        default_templates
                    )
                    await db.commit()

    # --- User Operations ---
    async def get_or_create_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user = await cursor.fetchone()
                if user:
                    # Update username/first_name if changed
                    await db.execute(
                        "UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
                        (username, first_name, user_id)
                    )
                    await db.commit()
                    return dict(user)
                
                await db.execute(
                    "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                    (user_id, username, first_name)
                )
                await db.commit()
                async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur2:
                    return dict(await cur2.fetchone())

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def add_balance(self, user_id: int, amount: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
            async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def deduct_balance(self, user_id: int, amount: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
                res = await cursor.fetchone()
                if not res or res[0] < amount:
                    return False
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
            return True

    async def get_all_users(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users ORDER BY created_at DESC") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # --- App Operations ---
    async def register_app(
        self,
        user_id: int,
        heroku_app_name: str,
        display_name: str,
        repo_url: Optional[str] = None,
        dyno_type: str = "worker",
        duration_days: int = 30,
        is_admin_app: bool = False
    ) -> int:
        expires_at = datetime.utcnow() + timedelta(days=duration_days) if not is_admin_app else None
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO apps 
                   (user_id, heroku_app_name, display_name, repo_url, dyno_type, status, expires_at, is_admin_app) 
                   VALUES (?, ?, ?, ?, ?, 'running', ?, ?)""",
                (user_id, heroku_app_name, display_name, repo_url, dyno_type, expires_at, 1 if is_admin_app else 0)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_user_apps(self, user_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM apps WHERE user_id = ? ORDER BY id DESC", (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_app_by_name(self, heroku_app_name: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM apps WHERE heroku_app_name = ?", (heroku_app_name,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_app_by_id(self, app_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM apps WHERE id = ?", (app_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_app_status(self, app_id: int, status: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE apps SET status = ? WHERE id = ?", (status, app_id))
            await db.commit()

    async def extend_app_subscription(self, app_id: int, days: int = 30) -> datetime:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT expires_at FROM apps WHERE id = ?", (app_id,)) as cursor:
                res = await cursor.fetchone()
                now = datetime.utcnow()
                if res and res[0]:
                    current_exp = datetime.fromisoformat(res[0])
                    new_exp = max(now, current_exp) + timedelta(days=days)
                else:
                    new_exp = now + timedelta(days=days)
                
                await db.execute("UPDATE apps SET expires_at = ?, status = 'running' WHERE id = ?", (new_exp, app_id))
                await db.commit()
                return new_exp

    async def delete_app_record(self, app_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM apps WHERE id = ?", (app_id,))
            await db.commit()

    async def get_all_active_apps(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM apps ORDER BY id DESC") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_expired_apps(self) -> List[Dict[str, Any]]:
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM apps WHERE is_admin_app = 0 AND expires_at <= ? AND status != 'stopped'", 
                (now,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # --- Payment Operations ---
    async def create_payment_request(self, user_id: int, amount: int, utr_number: Optional[str] = None, screenshot_file_id: Optional[str] = None) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO payments (user_id, amount, utr_number, screenshot_file_id, status) VALUES (?, ?, ?, ?, 'pending')",
                (user_id, amount, utr_number, screenshot_file_id)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_payment(self, payment_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_payment_status(self, payment_id: int, status: str, reviewed_by: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.utcnow().isoformat()
            await db.execute(
                "UPDATE payments SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?",
                (status, reviewed_by, now, payment_id)
            )
            await db.commit()
            return True

    # --- Template Operations ---
    async def get_templates(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM templates") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_template_by_id(self, template_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM templates WHERE id = ?", (template_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

db = Database()
