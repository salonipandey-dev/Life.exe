"""XP and coin ledgers. Append-only: rows are inserted, never updated."""

from __future__ import annotations

from dataclasses import dataclass

from lifeexe.core.db import Connection, Row


@dataclass(frozen=True)
class NewXpEvent:
    user_id: int
    amount: int
    base_amount: int
    reason: str
    source_type: str
    source_id: int | None
    skill_id: int | None
    attribute: str | None
    idempotency_key: str
    local_date: str
    created_at: str
    reverses_event_id: int | None = None


def insert_xp_event(conn: Connection, e: NewXpEvent) -> int:
    cur = conn.execute(
        """INSERT INTO xp_events (user_id, amount, base_amount, reason, source_type, source_id,
                                  skill_id, attribute, idempotency_key, reverses_event_id,
                                  local_date, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            e.user_id,
            e.amount,
            e.base_amount,
            e.reason,
            e.source_type,
            e.source_id,
            e.skill_id,
            e.attribute,
            e.idempotency_key,
            e.reverses_event_id,
            e.local_date,
            e.created_at,
        ),
    )
    return int(cur.lastrowid or 0)


def get_xp_event(conn: Connection, user_id: int, event_id: int) -> Row | None:
    row: Row | None = conn.execute(
        "SELECT * FROM xp_events WHERE user_id = ? AND id = ?", (user_id, event_id)
    ).fetchone()
    return row


def award_for_source(conn: Connection, user_id: int, source_type: str, source_id: int) -> Row | None:
    """The latest award (non-reversal) event for a source that has not been reversed."""
    row: Row | None = conn.execute(
        """SELECT e.* FROM xp_events e
            WHERE e.user_id = ? AND e.source_type = ? AND e.source_id = ?
              AND e.reverses_event_id IS NULL
              AND NOT EXISTS (SELECT 1 FROM xp_events r WHERE r.reverses_event_id = e.id)
            ORDER BY e.id DESC LIMIT 1""",
        (user_id, source_type, source_id),
    ).fetchone()
    return row


def count_awards_for_source(conn: Connection, user_id: int, source_type: str, source_id: int) -> int:
    return int(
        conn.execute(
            """SELECT COUNT(*) FROM xp_events
                WHERE user_id = ? AND source_type = ? AND source_id = ? AND reverses_event_id IS NULL""",
            (user_id, source_type, source_id),
        ).fetchone()[0]
    )


def total_xp(conn: Connection, user_id: int) -> int:
    return int(
        conn.execute("SELECT COALESCE(SUM(amount), 0) FROM xp_events WHERE user_id = ?", (user_id,)).fetchone()[0]
    )


def net_xp_on(conn: Connection, user_id: int, local_date: str) -> int:
    return int(
        conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM xp_events WHERE user_id = ? AND local_date = ?",
            (user_id, local_date),
        ).fetchone()[0]
    )


def xp_by_day(conn: Connection, user_id: int, start: str, end: str) -> dict[str, int]:
    rows = conn.execute(
        """SELECT local_date, SUM(amount) FROM xp_events
            WHERE user_id = ? AND local_date BETWEEN ? AND ?
            GROUP BY local_date""",
        (user_id, start, end),
    ).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def xp_by_attribute(conn: Connection, user_id: int, start: str | None = None, end: str | None = None) -> dict[str, int]:
    sql = "SELECT COALESCE(attribute, 'UNASSIGNED'), SUM(amount) FROM xp_events WHERE user_id = ?"
    params: list[object] = [user_id]
    if start and end:
        sql += " AND local_date BETWEEN ? AND ?"
        params += [start, end]
    rows = conn.execute(sql + " GROUP BY 1", params).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def xp_by_skill(conn: Connection, user_id: int, start: str | None = None, end: str | None = None) -> dict[int, int]:
    sql = "SELECT skill_id, SUM(amount) FROM xp_events WHERE user_id = ? AND skill_id IS NOT NULL"
    params: list[object] = [user_id]
    if start and end:
        sql += " AND local_date BETWEEN ? AND ?"
        params += [start, end]
    rows = conn.execute(sql + " GROUP BY skill_id", params).fetchall()
    return {int(r[0]): int(r[1]) for r in rows}


def recent_xp_events(conn: Connection, user_id: int, limit: int) -> list[Row]:
    return conn.execute(
        """SELECT e.*, q.title AS quest_title, h.name AS habit_name
             FROM xp_events e
             LEFT JOIN quest_completions c ON e.source_type = 'QUEST_COMPLETION' AND c.id = e.source_id
             LEFT JOIN quests q ON q.id = c.quest_id
             LEFT JOIN habit_logs hl ON e.source_type = 'HABIT_LOG' AND hl.id = e.source_id
             LEFT JOIN habits h ON h.id = hl.habit_id
            WHERE e.user_id = ?
            ORDER BY e.id DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()


# --- coins --------------------------------------------------------------------


def insert_coin_tx(
    conn: Connection, user_id: int, amount: int, reason: str, xp_event_id: int | None, key: str, now: str
) -> int:
    cur = conn.execute(
        """INSERT INTO coin_transactions (user_id, amount, reason, xp_event_id, idempotency_key, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, amount, reason, xp_event_id, key, now),
    )
    return int(cur.lastrowid or 0)


def coin_tx_for_xp_event(conn: Connection, user_id: int, xp_event_id: int) -> Row | None:
    row: Row | None = conn.execute(
        "SELECT * FROM coin_transactions WHERE user_id = ? AND xp_event_id = ? AND amount > 0",
        (user_id, xp_event_id),
    ).fetchone()
    return row


def coin_balance(conn: Connection, user_id: int) -> int:
    return int(
        conn.execute("SELECT COALESCE(SUM(amount), 0) FROM coin_transactions WHERE user_id = ?", (user_id,)).fetchone()[
            0
        ]
    )
