from __future__ import annotations

from lifeexe.core.db import Connection, Row
from lifeexe.repositories import build_update

PROFILE_COLUMNS = ("display_name", "title", "avatar", "theme", "timezone", "day_start_hour", "updated_at")


def create_user(conn: Connection, email: str, password_hash: str, now: str) -> int:
    cur = conn.execute(
        "INSERT INTO users (email, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (email, password_hash, now, now),
    )
    return int(cur.lastrowid or 0)


def get_user_by_email(conn: Connection, email: str) -> Row | None:
    row: Row | None = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return row


def get_user(conn: Connection, user_id: int) -> Row | None:
    row: Row | None = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return row


def update_password(conn: Connection, user_id: int, password_hash: str, now: str) -> None:
    conn.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?", (password_hash, now, user_id)
    )


def delete_user(conn: Connection, user_id: int) -> None:
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def create_profile(
    conn: Connection, user_id: int, display_name: str, title: str, avatar: str, timezone: str, now: str
) -> None:
    conn.execute(
        """INSERT INTO profiles (user_id, display_name, title, avatar, timezone, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, display_name, title, avatar, timezone, now, now),
    )


def get_profile(conn: Connection, user_id: int) -> Row | None:
    row: Row | None = conn.execute(
        """SELECT p.*, u.email, u.created_at AS account_created_at
             FROM profiles p JOIN users u ON u.id = p.user_id
            WHERE p.user_id = ?""",
        (user_id,),
    ).fetchone()
    return row


def update_profile(conn: Connection, user_id: int, fields: dict[str, object]) -> None:
    sql, params = build_update("profiles", PROFILE_COLUMNS, fields)
    conn.execute(sql + " WHERE user_id = ?", (*params, user_id))


# --- sessions -----------------------------------------------------------------

def create_session(conn: Connection, user_id: int, token_hash: str, now: str, expires_at: str) -> int:
    cur = conn.execute(
        """INSERT INTO sessions (user_id, token_hash, created_at, expires_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, token_hash, now, expires_at, now),
    )
    return int(cur.lastrowid or 0)


def get_session(conn: Connection, token_hash: str) -> Row | None:
    row: Row | None = conn.execute(
        "SELECT * FROM sessions WHERE token_hash = ?", (token_hash,)
    ).fetchone()
    return row


def delete_session(conn: Connection, token_hash: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def delete_other_sessions(conn: Connection, user_id: int, keep_token_hash: str | None) -> None:
    conn.execute(
        "DELETE FROM sessions WHERE user_id = ? AND token_hash IS NOT ?", (user_id, keep_token_hash)
    )


def purge_expired_sessions(conn: Connection, now: str) -> int:
    return conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,)).rowcount
