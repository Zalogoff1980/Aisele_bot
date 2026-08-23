import sqlite3
from datetime import datetime, timezone


DB_PATH = "aisele.db"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def init_initiative():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS initiative (
                user_id INTEGER PRIMARY KEY,
                last_at TEXT
            )
            """
        )


def get_last_initiative(user_id):
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            """
            SELECT last_at
            FROM initiative
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    if not row:
        return None

    return row[0]


def save_initiative(user_id):
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            INSERT INTO initiative (user_id, last_at)
            VALUES (?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                last_at = excluded.last_at
            """,
            (
                user_id,
                now_iso(),
            ),
        )
