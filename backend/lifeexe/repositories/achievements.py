from __future__ import annotations

from lifeexe.core.db import Connection, Row


def unlocked(conn: Connection, user_id: int) -> list[Row]:
    return conn.execute(
        "SELECT * FROM user_achievements WHERE user_id = ? ORDER BY unlocked_at DESC, achievement_key",
        (user_id,),
    ).fetchall()


def insert_if_missing(conn: Connection, user_id: int, key: str, now: str) -> bool:
    """Idempotent: returns True only when the row was newly inserted."""
    cur = conn.execute(
        """INSERT INTO user_achievements (user_id, achievement_key, unlocked_at) VALUES (?, ?, ?)
           ON CONFLICT (user_id, achievement_key) DO NOTHING""",
        (user_id, key, now),
    )
    return cur.rowcount == 1


def quest_completion_stats(conn: Connection, user_id: int) -> tuple[int, int, int]:
    row = conn.execute(
        """SELECT COUNT(*),
                  COALESCE(SUM(CASE WHEN q.difficulty = 'EPIC' THEN 1 ELSE 0 END), 0),
                  COALESCE(SUM(CASE WHEN q.category = 'BOSS' THEN 1 ELSE 0 END), 0)
             FROM quest_completions c JOIN quests q ON q.id = c.quest_id
            WHERE c.user_id = ? AND c.reversed_at IS NULL""",
        (user_id,),
    ).fetchone()
    return int(row[0]), int(row[1]), int(row[2])
