import sqlite3
from datetime import datetime, timedelta
from typing import Optional


class URLStorage:
    def __init__(self, db_path: str = "urls.db"):
        self.db_path = db_path
        self._conn = None
        if db_path == ":memory:":
            self._conn = sqlite3.connect(db_path)
            self._init_db(self._conn)
        else:
            conn = sqlite3.connect(db_path)
            self._init_db(conn)
            conn.close()

    def _get_conn(self):
        if self._conn is not None:
            return self._conn
        return sqlite3.connect(self.db_path)

    def _init_db(self, conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS url_mappings (
                short_code TEXT PRIMARY KEY,
                long_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                click_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS click_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT NOT NULL,
                ip TEXT,
                user_agent TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (short_code) REFERENCES url_mappings(short_code)
            )
        """)
        conn.commit()

    def save_mapping(self, short_code: str, long_url: str, ttl: Optional[int] = None) -> bool:
        expires_at = None
        if ttl:
            expires_at = datetime.now() + timedelta(seconds=ttl)

        try:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO url_mappings (short_code, long_url, expires_at) VALUES (?, ?, ?)",
                (short_code, long_url, expires_at)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_long_url(self, short_code: str) -> Optional[str]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT long_url, expires_at FROM url_mappings WHERE short_code = ?",
            (short_code,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        long_url, expires_at = row
        if expires_at and datetime.now() > datetime.fromisoformat(expires_at):
            return None

        return long_url

    def delete_mapping(self, short_code: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM url_mappings WHERE short_code = ?",
            (short_code,)
        )
        conn.commit()
        return cursor.rowcount > 0
