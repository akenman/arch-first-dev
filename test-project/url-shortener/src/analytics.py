import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any


class Analytics:
    def __init__(self, db_path: str = "urls.db", conn=None):
        self.db_path = db_path
        self._conn = conn

    def _get_conn(self):
        if self._conn is not None:
            return self._conn
        return sqlite3.connect(self.db_path)

    def record_click(self, short_code: str, ip: Optional[str] = None,
                     user_agent: Optional[str] = None) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE url_mappings SET click_count = click_count + 1 WHERE short_code = ?",
            (short_code,)
        )
        conn.execute(
            "INSERT INTO click_events (short_code, ip, user_agent) VALUES (?, ?, ?)",
            (short_code, ip, user_agent)
        )
        conn.commit()

    def get_stats(self, short_code: str) -> Dict[str, Any]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT click_count FROM url_mappings WHERE short_code = ?",
            (short_code,)
        )
        row = cursor.fetchone()
        if not row:
            return {"clicks": 0, "last_click": None}

        clicks = row[0]

        cursor = conn.execute(
            "SELECT MAX(timestamp) FROM click_events WHERE short_code = ?",
            (short_code,)
        )
        last_click_row = cursor.fetchone()
        last_click = last_click_row[0] if last_click_row and last_click_row[0] else None

        return {
            "clicks": clicks,
            "last_click": datetime.fromisoformat(last_click) if last_click else None
        }
