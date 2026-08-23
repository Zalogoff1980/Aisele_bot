import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path("aisele.db")


# ============================================================
# COMMON
# ============================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


# ============================================================
# DATABASE
# ============================================================

def init_database():

    with get_connection() as connection:

        # ----------------------------------------------------
        # USERS
        # ----------------------------------------------------

        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                telegram_name TEXT,
                display_name TEXT,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)

        # ----------------------------------------------------
        # MESSAGES
        # ----------------------------------------------------

        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # ----------------------------------------------------
        # MEMORIES
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # RELATIONSHIP
        # ----------------------------------------------------

        connection.execute("""
            CREATE TABLE IF NOT EXISTS relationship (
                user_id INTEGER PRIMARY KEY,
                trust INTEGER DEFAULT 0,
                closeness INTEGER DEFAULT 0,
                mood TEXT DEFAULT 'нейтральное',
                updated_at TEXT NOT NULL
            )
        """)

        # ----------------------------------------------------
        # WEATHER CONTEXT
        # ----------------------------------------------------
        # Храним последний город пользователя.
        # Это нужно для:
        #
        # "Какая погода в Навои?"
        # "А завтра?"
        # "А послезавтра?"
        #
        # Тогда "завтра" относится к Навои,
        # а не требует заново угадывать город.
        # ----------------------------------------------------

        connection.execute("""
            CREATE TABLE IF NOT EXISTS weather_context (
                user_id INTEGER PRIMARY KEY,
                location TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # ----------------------------------------------------
        # COMPATIBILITY WITH OLD DATABASE
        # ----------------------------------------------------

        columns = connection.execute(
            "PRAGMA table_info(users)"
        ).fetchall()

        column_names = {
            column["name"]
            for column in columns
        }

        if "display_name" not in column_names:

            connection.execute("""
                ALTER TABLE users
                ADD COLUMN display_name TEXT
            """)


# ============================================================
# USERS
# ============================================================

def ensure_user(
    user_id,
    telegram_name=None,
    display_name=None,
):

    now = now_iso()

    with get_connection() as connection:

        user = connection.execute(
            """
            SELECT
                user_id,
                telegram_name,
                display_name
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
                    display_name,
                    created_at,
                    last_seen
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    telegram_name,
                    display_name,
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

            new_display_name = (
                display_name
                if display_name
                else user["display_name"]
            )

            connection.execute(
                """
                UPDATE users
                SET
                    telegram_name = ?,
                    display_name = ?,
                    last_seen = ?
                WHERE user_id = ?
                """,
                (
                    telegram_name,
                    new_display_name,
                    now,
                    user_id,
                ),
            )


def get_user(
    user_id,
):

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT
                user_id,
                telegram_name,
                display_name,
                created_at,
                last_seen
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "user_id": row["user_id"],
        "telegram_name": row["telegram_name"],
        "display_name": row["display_name"],
        "created_at": row["created_at"],
        "last_seen": row["last_seen"],
    }


def get_display_name(
    user_id,
):

    user = get_user(
        user_id
    )

    if not user:
        return None

    name = (
        user.get("display_name")
        or ""
    ).strip()

    if not name:
        return None

    return name


def set_display_name(
    user_id,
    display_name,
):

    display_name = (
        display_name or ""
    ).strip()

    if not display_name:
        return False

    if len(display_name) > 100:
        display_name = display_name[:100]

    with get_connection() as connection:

        cursor = connection.execute(
            """
            UPDATE users
            SET display_name = ?
            WHERE user_id = ?
            """,
            (
                display_name,
                user_id,
            ),
        )

        return cursor.rowcount > 0


# ============================================================
# MESSAGES
# ============================================================

def save_message(
    user_id,
    role,
    content,
):

    content = (
        content or ""
    ).strip()

    if not content:
        return False

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

    return True


def clear_messages(
    user_id,
):

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
            SELECT
                role,
                content
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

    rows = list(
        reversed(rows)
    )

    return [
        {
            "role": row["role"],
            "content": row["content"],
        }
        for row in rows
    ]


# ============================================================
# MEMORIES
# ============================================================

def save_memory(
    user_id,
    category,
    content,
    importance=5,
):

    content = (
        content or ""
    ).strip()

    if not content:
        return False

    importance = max(
        1,
        min(10, int(importance)),
    )

    with get_connection() as connection:

        existing = connection.execute(
            """
            SELECT id
            FROM memories
            WHERE user_id = ?
              AND LOWER(TRIM(content)) =
                  LOWER(TRIM(?))
            LIMIT 1
            """,
            (
                user_id,
                content,
            ),
        ).fetchone()

        if existing is not None:

            connection.execute(
                """
                UPDATE memories
                SET
                    importance =
                        MAX(importance, ?)
                WHERE id = ?
                """,
                (
                    importance,
                    existing["id"],
                ),
            )

            return False

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

    return True


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


def delete_memory(
    user_id,
    content,
):

    content = (
        content or ""
    ).strip()

    if not content:
        return False

    with get_connection() as connection:

        cursor = connection.execute(
            """
            DELETE FROM memories
            WHERE user_id = ?
              AND LOWER(TRIM(content)) =
                  LOWER(TRIM(?))
            """,
            (
                user_id,
                content,
            ),
        )

        return cursor.rowcount > 0


def clear_memories(
    user_id,
):

    with get_connection() as connection:

        connection.execute(
            """
            DELETE FROM memories
            WHERE user_id = ?
            """,
            (user_id,),
        )


# ============================================================
# RELATIONSHIP
# ============================================================

def get_relationship(
    user_id,
):

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

    current = get_relationship(
        user_id
    )

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
            INSERT INTO relationship
            (
                user_id,
                trust,
                closeness,
                mood,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                trust = excluded.trust,
                closeness = excluded.closeness,
                mood = excluded.mood,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                trust,
                closeness,
                mood,
                now_iso(),
            ),
        )


# ============================================================
# WEATHER CONTEXT
# ============================================================

def save_weather_context(
    user_id,
    location,
):

    location = (
        location or ""
    ).strip()

    if not location:
        return False

    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO weather_context
            (
                user_id,
                location,
                updated_at
            )
            VALUES (?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                location = excluded.location,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                location,
                now_iso(),
            ),
        )

    return True


def get_weather_context(
    user_id,
):

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT
                location,
                updated_at
            FROM weather_context
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "location": row["location"],
        "updated_at": row["updated_at"],
    }


def clear_weather_context(
    user_id,
):

    with get_connection() as connection:

        connection.execute(
            """
            DELETE FROM weather_context
            WHERE user_id = ?
            """,
            (user_id,),
        )


# ============================================================
# END
# ============================================================
