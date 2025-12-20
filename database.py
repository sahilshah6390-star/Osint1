import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from config import REFERRAL_REWARD_DIAMOND


class Database:
    def __init__(self, db_name: str = "osint_bot.db"):
        self.db_name = db_name
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                credits INTEGER DEFAULT 0,
                diamonds INTEGER DEFAULT 0,
                referrer_id INTEGER,
                referred_count INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                daily_search_count INTEGER DEFAULT 0,
                vhowner_daily_count INTEGER DEFAULT 0,
                last_search_date TEXT,
                last_verify_time TEXT,
                joined_date TEXT,
                last_active TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                date TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS protected_numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT UNIQUE,
                added_by INTEGER,
                added_date TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT UNIQUE,
                type TEXT,
                added_by INTEGER,
                added_date TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS search_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                search_type TEXT,
                query TEXT,
                timestamp TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS redeem_codes (
                code TEXT PRIMARY KEY,
                code_type TEXT,
                amount INTEGER,
                used_by INTEGER,
                used_at TEXT
            )
            """
        )

        # Migration helpers
        self._ensure_column(cursor, "users", "credits", "INTEGER DEFAULT 0")
        self._ensure_column(cursor, "users", "diamonds", "INTEGER DEFAULT 0")
        self._ensure_column(cursor, "users", "referrer_id", "INTEGER")
        self._ensure_column(cursor, "users", "referred_count", "INTEGER DEFAULT 0")
        self._ensure_column(cursor, "users", "daily_search_count", "INTEGER DEFAULT 0")
        self._ensure_column(cursor, "users", "vhowner_daily_count", "INTEGER DEFAULT 0")
        self._ensure_column(cursor, "users", "last_search_date", "TEXT")
        self._ensure_column(cursor, "users", "last_verify_time", "TEXT")

        self._ensure_redeem_columns(cursor)

        conn.commit()
        conn.close()

    def _ensure_column(self, cursor: sqlite3.Cursor, table: str, column: str, definition: str):
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        if column not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    # Users
    def add_user(self, user_id: int, username: str = None, first_name: str = None, referrer_id: int = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO users (user_id, username, first_name, referrer_id, joined_date, last_active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, first_name, referrer_id, datetime.now().isoformat(), datetime.now().isoformat()),
            )

            if referrer_id:
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,))
                ref_exists = cursor.fetchone()
                if ref_exists:
                    cursor.execute(
                        "INSERT INTO referrals (referrer_id, referred_id, date) VALUES (?, ?, ?)",
                        (referrer_id, user_id, datetime.now().isoformat()),
                    )
                    cursor.execute(
                        "UPDATE users SET referred_count = referred_count + 1, diamonds = diamonds + ? WHERE user_id = ?",
                        (REFERRAL_REWARD_DIAMOND, referrer_id),
                    )

            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_user(self, user_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def ensure_daily_counter(self, user_id: int) -> Dict:
        user = self.get_user(user_id)
        if not user:
            return {}
        today = datetime.now().strftime("%Y-%m-%d")
        if user.get("last_search_date") != today:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET daily_search_count = 0, vhowner_daily_count = 0, last_search_date = ? WHERE user_id = ?",
                (today, user_id),
            )
            conn.commit()
            conn.close()
            user["daily_search_count"] = 0
            user["vhowner_daily_count"] = 0
            user["last_search_date"] = today
        return user

    def can_verify_now(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user:
            return True  # Allow if user not found, but should be registered
        last_verify = user.get("last_verify_time")
        if not last_verify:
            return True
        try:
            last_time = datetime.fromisoformat(last_verify)
            now = datetime.now()
            diff = (now - last_time).total_seconds()
            return diff >= 30
        except ValueError:
            return True

    def update_last_verify_time(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_verify_time = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()

    def update_last_active(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()

    def update_diamonds(self, user_id: int, amount: int, operation: str = "add") -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        if operation == "add":
            cursor.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id = ?", (amount, user_id))
        elif operation == "deduct":
            cursor.execute(
                "UPDATE users SET diamonds = diamonds - ? WHERE user_id = ? AND diamonds >= ?",
                (amount, user_id, amount),
            )
        elif operation == "set":
            cursor.execute("UPDATE users SET diamonds = ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success

    def update_credits(self, user_id: int, amount: int, operation: str = "add") -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        if operation == "add":
            cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
        elif operation == "deduct":
            cursor.execute(
                "UPDATE users SET credits = credits - ? WHERE user_id = ? AND credits >= ?",
                (amount, user_id, amount),
            )
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success

    def ban_user(self, user_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success

    def unban_user(self, user_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success

    def is_banned(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        return bool(user and user.get("is_banned"))

    def has_logged_start(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        return bool(user and user.get("joined_date"))

    # Protected & blacklist
    def add_protected_number(self, number: str, added_by: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO protected_numbers (number, added_by, added_date) VALUES (?, ?, ?)",
                (number, added_by, datetime.now().isoformat()),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def is_protected(self, number: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM protected_numbers WHERE number = ?", (number,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def add_to_blacklist(self, identifier: str, type: str, added_by: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO blacklist (identifier, type, added_by, added_date) VALUES (?, ?, ?, ?)",
                (identifier, type, added_by, datetime.now().isoformat()),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def is_blacklisted(self, identifier: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM blacklist WHERE identifier = ?", (identifier,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    # Redeem codes
    def _ensure_redeem_columns(self, cursor: sqlite3.Cursor):
        cursor.execute("PRAGMA table_info(redeem_codes)")
        existing = {row[1] for row in cursor.fetchall()}
        if "code_type" not in existing:
            cursor.execute("ALTER TABLE redeem_codes ADD COLUMN code_type TEXT")
        if "amount" not in existing:
            cursor.execute("ALTER TABLE redeem_codes ADD COLUMN amount INTEGER")

    def create_redeem_code(self, code: str, amount: int, code_type: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO redeem_codes (code, code_type, amount) VALUES (?, ?, ?)",
                (code.upper(), code_type, amount),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def redeem_code(self, user_id: int, code: str) -> (bool, str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT code, code_type, amount, used_by FROM redeem_codes WHERE code = ?", (code.upper(),))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "Invalid code."
        if row["used_by"]:
            conn.close()
            return False, "Code already used."

        code_type = row["code_type"]
        amount = row["amount"] or 0
        if code_type == "diamonds":
            cursor.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id = ?", (amount, user_id))
        else:
            cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
        cursor.execute(
            "UPDATE redeem_codes SET used_by = ?, used_at = ? WHERE code = ?",
            (user_id, datetime.now().isoformat(), code.upper()),
        )
        conn.commit()
        conn.close()
        return True, f"Redeemed {amount} {code_type}."

    # Logging & stats
    def log_search(self, user_id: int, search_type: str, query: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO search_logs (user_id, search_type, query, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, search_type, query, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def get_all_user_ids(self) -> List[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def get_stats(self) -> Dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM search_logs")
        total_searches = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
        banned_users = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(referred_count),0) FROM users")
        total_referrals = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(diamonds),0) FROM users")
        total_diamonds = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(credits),0) FROM users")
        total_credits = cursor.fetchone()[0]
        conn.close()
        return {
            "total_users": total_users,
            "total_searches": total_searches,
            "banned_users": banned_users,
            "total_referrals": total_referrals,
            "total_diamonds": total_diamonds,
            "total_credits": total_credits,
        }
