from __future__ import annotations

from typing import Any

from lifeexe.core.db import Connection, Row
from lifeexe.repositories import build_update

UPDATABLE = (
    "name", "description", "schedule_kind", "weekdays_mask", "target_per_week", "measure",
    "target_value", "attribute", "archived_at", "updated_at",
)


def insert(conn: Connection, user_id: int, fields: dict[str, Any]) -> int:
    cols = ["user_id", *fields.keys()]
    cur = conn.execute(
        f"INSERT INTO habits ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        (user_id, *fields.values()),
    )
    return int(cur.lastrowid or 0)


def get(conn: Connection, user_id: int, habit_id: int) -> Row | None:
    row: Row | None = conn.execute(
        "SELECT * FROM habits WHERE user_id = ? AND id = ?", (user_id, habit_id)
    ).fetchone()
    return row


def list_habits(conn: Connection, user_id: int, include_archived: bool) -> list[Row]:
    sql = "SELECT * FROM habits WHERE user_id = ?"
    if not include_archived:
        sql += " AND archived_at IS NULL"
    return conn.execute(sql + " ORDER BY created_at, id", (user_id,)).fetchall()


def update(conn: Connection, user_id: int, habit_id: int, fields: dict[str, Any]) -> None:
    sql, params = build_update("habits", UPDATABLE, fields)
    conn.execute(sql + " WHERE id = ? AND user_id = ?", (*params, habit_id, user_id))


def logs_for_habits(conn: Connection, user_id: int, habit_ids: list[int]) -> list[Row]:
    if not habit_ids:
        return []
    marks = ", ".join("?" for _ in habit_ids)
    return conn.execute(
        f"SELECT * FROM habit_logs WHERE user_id = ? AND habit_id IN ({marks}) ORDER BY local_date",
        (user_id, *habit_ids),
    ).fetchall()


def get_log(conn: Connection, user_id: int, habit_id: int, local_date: str) -> Row | None:
    row: Row | None = conn.execute(
        "SELECT * FROM habit_logs WHERE user_id = ? AND habit_id = ? AND local_date = ?",
        (user_id, habit_id, local_date),
    ).fetchone()
    return row


def insert_log(conn: Connection, user_id: int, habit_id: int, local_date: str, entry_type: str,
               value: int, note: str, now: str) -> int:
    cur = conn.execute(
        """INSERT INTO habit_logs (user_id, habit_id, local_date, entry_type, value, note, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, habit_id, local_date, entry_type, value, note, now, now),
    )
    return int(cur.lastrowid or 0)


def update_log(conn: Connection, user_id: int, log_id: int, entry_type: str, value: int, note: str, now: str) -> None:
    conn.execute(
        """UPDATE habit_logs SET entry_type = ?, value = ?, note = ?, updated_at = ?
            WHERE id = ? AND user_id = ?""",
        (entry_type, value, note, now, log_id, user_id),
    )


def set_award(conn: Connection, user_id: int, log_id: int, event_id: int | None) -> None:
    conn.execute(
        "UPDATE habit_logs SET award_event_id = ? WHERE id = ? AND user_id = ?", (event_id, log_id, user_id)
    )


def delete_log(conn: Connection, user_id: int, log_id: int) -> None:
    conn.execute("DELETE FROM habit_logs WHERE id = ? AND user_id = ?", (log_id, user_id))


def pauses_for_habits(conn: Connection, user_id: int, habit_ids: list[int]) -> list[Row]:
    if not habit_ids:
        return []
    marks = ", ".join("?" for _ in habit_ids)
    return conn.execute(
        f"SELECT * FROM habit_pauses WHERE user_id = ? AND habit_id IN ({marks}) ORDER BY start_date",
        (user_id, *habit_ids),
    ).fetchall()


def open_pause(conn: Connection, user_id: int, habit_id: int) -> Row | None:
    row: Row | None = conn.execute(
        "SELECT * FROM habit_pauses WHERE user_id = ? AND habit_id = ? AND end_date IS NULL",
        (user_id, habit_id),
    ).fetchone()
    return row


def start_pause(conn: Connection, user_id: int, habit_id: int, start: str) -> None:
    conn.execute(
        "INSERT INTO habit_pauses (user_id, habit_id, start_date) VALUES (?, ?, ?)", (user_id, habit_id, start)
    )


def end_pause(conn: Connection, user_id: int, pause_id: int, end: str | None) -> None:
    if end is None:
        conn.execute("DELETE FROM habit_pauses WHERE id = ? AND user_id = ?", (pause_id, user_id))
    else:
        conn.execute(
            "UPDATE habit_pauses SET end_date = ? WHERE id = ? AND user_id = ?", (end, pause_id, user_id)
        )


def done_days_count(conn: Connection, user_id: int) -> int:
    return int(
        conn.execute(
            """SELECT COUNT(*) FROM habit_logs l JOIN habits h ON h.id = l.habit_id
                WHERE l.user_id = ? AND l.entry_type = 'ENTRY' AND l.value >= h.target_value""",
            (user_id,),
        ).fetchone()[0]
    )


def done_by_day(conn: Connection, user_id: int, start: str, end: str) -> dict[str, int]:
    rows = conn.execute(
        """SELECT l.local_date, COUNT(*) FROM habit_logs l JOIN habits h ON h.id = l.habit_id
            WHERE l.user_id = ? AND l.entry_type = 'ENTRY' AND l.value >= h.target_value
              AND l.local_date BETWEEN ? AND ?
            GROUP BY l.local_date""",
        (user_id, start, end),
    ).fetchall()
    return {r[0]: int(r[1]) for r in rows}
