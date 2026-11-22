from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lifeexe.core.db import Connection, Row
from lifeexe.repositories import build_update, escape_like

UPDATABLE = (
    "title",
    "description",
    "category",
    "priority",
    "difficulty",
    "status",
    "recurrence",
    "estimated_minutes",
    "due_date",
    "completion_criteria",
    "skill_id",
    "updated_at",
    "started_at",
    "completed_at",
    "archived_at",
)

#: Whitelisted sort keys -> ORDER BY fragments (never interpolate user input).
SORTS: dict[str, str] = {
    "created_at": "q.created_at ASC, q.id ASC",
    "-created_at": "q.created_at DESC, q.id DESC",
    "due_date": "(q.due_date IS NULL) ASC, q.due_date ASC, q.id ASC",
    "-due_date": "(q.due_date IS NULL) ASC, q.due_date DESC, q.id DESC",
    "priority": "prio ASC, q.id ASC",
    "-priority": "prio DESC, (q.due_date IS NULL) ASC, q.due_date ASC, q.id ASC",
    "title": "q.title COLLATE NOCASE ASC, q.id ASC",
}

_SELECT = """
SELECT q.*, s.name AS skill_name, s.attribute AS skill_attribute,
       CASE q.priority WHEN 'LOW' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'HIGH' THEN 3 ELSE 4 END AS prio,
       EXISTS (
         SELECT 1 FROM quest_completions c
          WHERE c.quest_id = q.id AND c.reversed_at IS NULL
            AND c.occurrence_key = CASE q.recurrence
                                     WHEN 'NONE' THEN 'once'
                                     WHEN 'DAILY' THEN :day_key
                                     ELSE :week_key END
       ) AS occurrence_completed,
       (SELECT COUNT(*) FROM quest_completions c2
         WHERE c2.quest_id = q.id AND c2.reversed_at IS NULL) AS completion_count
  FROM quests q
  LEFT JOIN skills s ON s.id = q.skill_id AND s.user_id = q.user_id
"""


@dataclass(frozen=True)
class QuestFilters:
    statuses: tuple[str, ...] = ()
    category: str | None = None
    difficulty: str | None = None
    search: str | None = None
    include_archived: bool = False
    sort: str = "-priority"
    limit: int = 50
    offset: int = 0


def insert(conn: Connection, user_id: int, fields: dict[str, Any]) -> int:
    cols = ["user_id", *fields.keys()]
    placeholders = ", ".join("?" for _ in cols)
    cur = conn.execute(
        f"INSERT INTO quests ({', '.join(cols)}) VALUES ({placeholders})",  # cols from service code
        (user_id, *fields.values()),
    )
    return int(cur.lastrowid or 0)


def get(conn: Connection, user_id: int, quest_id: int, day_key: str, week_key: str) -> Row | None:
    row: Row | None = conn.execute(
        _SELECT + " WHERE q.user_id = :user_id AND q.id = :quest_id",
        {"user_id": user_id, "quest_id": quest_id, "day_key": day_key, "week_key": week_key},
    ).fetchone()
    return row


def update(conn: Connection, user_id: int, quest_id: int, fields: dict[str, Any]) -> None:
    sql, params = build_update("quests", UPDATABLE, fields)
    conn.execute(sql + " WHERE id = ? AND user_id = ?", (*params, quest_id, user_id))


def delete(conn: Connection, user_id: int, quest_id: int) -> None:
    conn.execute("DELETE FROM quests WHERE id = ? AND user_id = ?", (quest_id, user_id))


def list_quests(conn: Connection, user_id: int, f: QuestFilters, day_key: str, week_key: str) -> tuple[list[Row], int]:
    where = ["q.user_id = :user_id"]
    params: dict[str, Any] = {"user_id": user_id, "day_key": day_key, "week_key": week_key}
    if f.statuses:
        names = []
        for i, status in enumerate(f.statuses):
            params[f"st{i}"] = status
            names.append(f":st{i}")
        where.append(f"q.status IN ({', '.join(names)})")
    if f.category:
        where.append("q.category = :category")
        params["category"] = f.category
    if f.difficulty:
        where.append("q.difficulty = :difficulty")
        params["difficulty"] = f.difficulty
    if f.search:
        where.append("(q.title LIKE :search ESCAPE '\\' OR q.description LIKE :search ESCAPE '\\')")
        params["search"] = f"%{escape_like(f.search)}%"
    if not f.include_archived:
        where.append("q.archived_at IS NULL")
    clause = " WHERE " + " AND ".join(where)
    total = int(conn.execute("SELECT COUNT(*) FROM quests q" + clause, params).fetchone()[0])
    order = SORTS[f.sort]
    params["limit"], params["offset"] = f.limit, f.offset
    rows = conn.execute(_SELECT + clause + f" ORDER BY {order} LIMIT :limit OFFSET :offset", params).fetchall()
    return rows, total


def today_candidates(conn: Connection, user_id: int, today: str, day_key: str, week_key: str) -> list[Row]:
    """Quests relevant today: recurring active ones, active ones, and anything
    available that is due today or overdue."""
    return conn.execute(
        _SELECT
        + """ WHERE q.user_id = :user_id AND q.archived_at IS NULL
                AND (
                     (q.recurrence <> 'NONE' AND q.status = 'ACTIVE')
                  OR (q.recurrence = 'NONE' AND q.status IN ('ACTIVE', 'PAUSED'))
                  OR (q.recurrence = 'NONE' AND q.status = 'AVAILABLE' AND q.due_date <= :today)
                  OR (q.recurrence = 'NONE' AND q.status = 'COMPLETED' AND EXISTS (
                        SELECT 1 FROM quest_completions c3
                         WHERE c3.quest_id = q.id AND c3.reversed_at IS NULL
                           AND c3.local_date = :today))
                )
              ORDER BY prio DESC, (q.due_date IS NULL) ASC, q.due_date ASC, q.id ASC""",
        {"user_id": user_id, "today": today, "day_key": day_key, "week_key": week_key},
    ).fetchall()


# --- completions ----------------------------------------------------------------


def live_completion(conn: Connection, user_id: int, quest_id: int, occurrence_key: str) -> Row | None:
    row: Row | None = conn.execute(
        """SELECT * FROM quest_completions
            WHERE user_id = ? AND quest_id = ? AND occurrence_key = ? AND reversed_at IS NULL""",
        (user_id, quest_id, occurrence_key),
    ).fetchone()
    return row


def insert_completion(
    conn: Connection, user_id: int, quest_id: int, occurrence_key: str, local_date: str, now: str
) -> int:
    cur = conn.execute(
        """INSERT INTO quest_completions (user_id, quest_id, occurrence_key, local_date, completed_at)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, quest_id, occurrence_key, local_date, now),
    )
    return int(cur.lastrowid or 0)


def reverse_completion(conn: Connection, user_id: int, completion_id: int, now: str) -> None:
    conn.execute(
        "UPDATE quest_completions SET reversed_at = ? WHERE id = ? AND user_id = ? AND reversed_at IS NULL",
        (now, completion_id, user_id),
    )


def has_any_completion(conn: Connection, user_id: int, quest_id: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM quest_completions WHERE user_id = ? AND quest_id = ? LIMIT 1", (user_id, quest_id)
        ).fetchone()
        is not None
    )


def completion_history(conn: Connection, user_id: int, quest_id: int, limit: int = 20) -> list[Row]:
    return conn.execute(
        """SELECT c.*, e.amount AS xp_awarded
             FROM quest_completions c
             LEFT JOIN xp_events e ON e.source_type = 'QUEST_COMPLETION' AND e.source_id = c.id
                                  AND e.reverses_event_id IS NULL
            WHERE c.user_id = ? AND c.quest_id = ?
            ORDER BY c.id DESC LIMIT ?""",
        (user_id, quest_id, limit),
    ).fetchall()
