"""Read-only aggregation queries over raw event tables.

Raw events (quest_completions, habit_logs, xp_events) are the source of truth;
everything here is derived on request and never stored, so there is nothing to
drift out of sync. Reversed completions are excluded everywhere.
"""

from __future__ import annotations

from lifeexe.core.db import Connection


def completions_by_day(conn: Connection, user_id: int, start: str, end: str) -> dict[str, int]:
    rows = conn.execute(
        """SELECT local_date, COUNT(*) FROM quest_completions
            WHERE user_id = ? AND reversed_at IS NULL AND local_date BETWEEN ? AND ?
            GROUP BY local_date""",
        (user_id, start, end),
    ).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def completions_by_category(conn: Connection, user_id: int, start: str, end: str) -> dict[str, int]:
    rows = conn.execute(
        """SELECT q.category, COUNT(*) FROM quest_completions c JOIN quests q ON q.id = c.quest_id
            WHERE c.user_id = ? AND c.reversed_at IS NULL AND c.local_date BETWEEN ? AND ?
            GROUP BY q.category""",
        (user_id, start, end),
    ).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def due_quest_rate(conn: Connection, user_id: int, start: str, end: str, today: str) -> tuple[int, int]:
    """(completed, counted) for one-off quests *due* in [start, end].

    Counted = due in range, not DRAFT/CANCELLED, and either already completed
    or with a due date before today (a quest due today or later is not yet a
    miss). Quests without a due date are excluded by definition.
    """
    row = conn.execute(
        """SELECT COALESCE(SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END), 0), COUNT(*)
             FROM quests
            WHERE user_id = ? AND recurrence = 'NONE' AND due_date BETWEEN ? AND ?
              AND status NOT IN ('DRAFT', 'CANCELLED')
              AND (status = 'COMPLETED' OR due_date < ?)""",
        (user_id, start, end, today),
    ).fetchone()
    return int(row[0]), int(row[1])
