import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path("aisele.db")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    with get_connection() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                telegram_name TEXT,
                display_name TEXT,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 5,
                created_at TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS relationship (
                user_id INTEGER PRIMARY KEY,
                trust INTEGER DEFAULT 0,
                closeness INTEGER DEFAULT 0,
                mood TEXT DEFAULT 'нейтральное',
                updated_at TEXT NOT NULL
            )
        """)


def ensure_user(user_id, telegram_name=None):
    now = now_iso()

    with get_connection() as connection:

        user = connection.execute(
            """
            SELECT user_id
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if user is None:

            connection.execute(
                """
                INSERT INTO users
                (
                    user_id,
                    telegram_name,
                    created_at,
                    last_seen
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    telegram_name,
                    now,
                    now,
                ),
            )

            connection.execute(
                """
                INSERT INTO relationship
                (
                    user_id,
                    trust,
                    closeness,
                    mood,
                    updated_at
                )
                VALUES (?, 0, 0, 'нейтральное', ?)
                """,
                (
                    user_id,
                    now,
                ),
            )

        else:

            connection.execute(
                """
                UPDATE users
                SET telegram_name = ?,
                    last_seen = ?
                WHERE user_id = ?
                """,
                (
                    telegram_name,
                    now,
                    user_id,
                ),
            )


def save_message(
    user_id,
    role,
    content,
):
    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO messages
            (
                user_id,
                role,
                content,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                role,
                content,
                now_iso(),
            ),
        )


def clear_messages(user_id):
    with get_connection() as connection:

        connection.execute(
            """
            DELETE FROM messages
            WHERE user_id = ?
            """,
            (user_id,),
        )


def get_recent_messages(
    user_id,
    limit=20,
):
    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT role, content
            FROM messages
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                user_id,
                limit,
            ),
        ).fetchall()

    rows = list(reversed(rows))

    return [
        {
            "role": row["role"],
            "content": row["content"],
        }
        for row in rows
    ]


def save_memory(
    user_id,
    category,
    content,
    importance=5,
):
    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO memories
            (
                user_id,
                category,
                content,
                importance,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                category,
                content,
                importance,
                now_iso(),
            ),
        )


def get_memories(
    user_id,
    limit=30,
):
    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                category,
                content,
                importance
            FROM memories
            WHERE user_id = ?
            ORDER BY importance DESC, id DESC
            LIMIT ?
            """,
            (
                user_id,
                limit,
            ),
        ).fetchall()

    return [
        {
            "category": row["category"],
            "content": row["content"],
            "importance": row["importance"],
        }
        for row in rows
    ]


def get_relationship(user_id):
    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT
                trust,
                closeness,
                mood
            FROM relationship
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return {
            "trust": 0,
            "closeness": 0,
            "mood": "нейтральное",
        }

    return {
        "trust": row["trust"],
        "closeness": row["closeness"],
        "mood": row["mood"],
    }


def update_relationship(
    user_id,
    trust=None,
    closeness=None,
    mood=None,
):
    current = get_relationship(user_id)

    trust = (
        current["trust"]
        if trust is None
        else trust
    )

    closeness = (
        current["closeness"]
        if closeness is None
        else closeness
    )

    mood = (
        current["mood"]
        if mood is None
        else mood
    )

    trust = max(
        0,
        min(100, int(trust)),
    )

    closeness = max(
        0,
        min(100, int(closeness)),
    )

    with get_connection() as connection:

        connection.execute(
            """
            UPDATE relationship
            SET
                trust = ?,
                closeness = ?,
                mood = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                trust,
                closeness,
                mood,
                now_iso(),
                user_id,
            ),
        )
