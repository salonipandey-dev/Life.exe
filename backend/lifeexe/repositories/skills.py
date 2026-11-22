from __future__ import annotations

from typing import Any

from lifeexe.core.db import Connection, Row
from lifeexe.repositories import build_update

UPDATABLE = ("name", "tree", "attribute", "description", "xp_required", "evidence_required", "archived_at")


def insert(conn: Connection, user_id: int, fields: dict[str, Any]) -> int:
    cols = ["user_id", *fields.keys()]
    cur = conn.execute(
        f"INSERT INTO skills ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        (user_id, *fields.values()),
    )
    return int(cur.lastrowid or 0)


def get(conn: Connection, user_id: int, skill_id: int) -> Row | None:
    row: Row | None = conn.execute("SELECT * FROM skills WHERE user_id = ? AND id = ?", (user_id, skill_id)).fetchone()
    return row


def slug_exists(conn: Connection, user_id: int, slug: str) -> bool:
    return conn.execute("SELECT 1 FROM skills WHERE user_id = ? AND slug = ?", (user_id, slug)).fetchone() is not None


def list_skills(conn: Connection, user_id: int, include_archived: bool = False) -> list[Row]:
    sql = """SELECT s.*, (SELECT COUNT(*) FROM skill_evidence e WHERE e.skill_id = s.id) AS evidence_count
               FROM skills s WHERE s.user_id = ?"""
    if not include_archived:
        sql += " AND s.archived_at IS NULL"
    return conn.execute(sql + " ORDER BY s.tree, s.name", (user_id,)).fetchall()


def update(conn: Connection, user_id: int, skill_id: int, fields: dict[str, Any]) -> None:
    sql, params = build_update("skills", UPDATABLE, fields)
    conn.execute(sql + " WHERE id = ? AND user_id = ?", (*params, skill_id, user_id))


def dependencies(conn: Connection, user_id: int) -> list[tuple[int, int]]:
    rows = conn.execute(
        "SELECT skill_id, prerequisite_id FROM skill_dependencies WHERE user_id = ?", (user_id,)
    ).fetchall()
    return [(int(r[0]), int(r[1])) for r in rows]


def add_dependency(conn: Connection, user_id: int, skill_id: int, prerequisite_id: int, now: str) -> None:
    conn.execute(
        """INSERT INTO skill_dependencies (user_id, skill_id, prerequisite_id, created_at)
           VALUES (?, ?, ?, ?)""",
        (user_id, skill_id, prerequisite_id, now),
    )


def remove_dependency(conn: Connection, user_id: int, skill_id: int, prerequisite_id: int) -> int:
    return conn.execute(
        "DELETE FROM skill_dependencies WHERE user_id = ? AND skill_id = ? AND prerequisite_id = ?",
        (user_id, skill_id, prerequisite_id),
    ).rowcount


def evidence_for_skill(conn: Connection, user_id: int, skill_id: int) -> list[Row]:
    return conn.execute(
        "SELECT * FROM skill_evidence WHERE user_id = ? AND skill_id = ? ORDER BY id DESC", (user_id, skill_id)
    ).fetchall()


def insert_evidence(
    conn: Connection, user_id: int, skill_id: int, title: str, url: str | None, notes: str, now: str
) -> int:
    cur = conn.execute(
        """INSERT INTO skill_evidence (user_id, skill_id, title, url, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, skill_id, title, url, notes, now),
    )
    return int(cur.lastrowid or 0)


def delete_evidence(conn: Connection, user_id: int, skill_id: int, evidence_id: int) -> int:
    return conn.execute(
        "DELETE FROM skill_evidence WHERE user_id = ? AND skill_id = ? AND id = ?", (user_id, skill_id, evidence_id)
    ).rowcount


def evidence_count(conn: Connection, user_id: int) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM skill_evidence WHERE user_id = ?", (user_id,)).fetchone()[0])
