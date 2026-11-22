"""Default skill catalog copied to each new account.

Each account gets its *own* editable copy, so nothing about one person's
career path is hard-coded for every user.
"""

from __future__ import annotations

import re

from lifeexe.core.db import Connection
from lifeexe.repositories import skills as skills_repo

INT, D, C, S, K, M, F, R = (
    "INTELLECT",
    "DISCIPLINE",
    "CREATIVITY",
    "STRENGTH",
    "KNOWLEDGE",
    "COMMUNICATION",
    "FINANCIAL_LITERACY",
    "CAREER_DEVELOPMENT",
)

# (tree, name, attribute, xp_required, evidence_required, prerequisites by name)
DEFAULT_SKILLS: tuple[tuple[str, str, str, int, int, tuple[str, ...]], ...] = (
    ("Data Analytics", "Excel", INT, 150, 1, ()),
    ("Data Analytics", "SQL", INT, 150, 1, ()),
    ("Data Analytics", "SQL Joins", INT, 200, 1, ("SQL",)),
    ("Data Analytics", "Python", INT, 150, 1, ()),
    ("Data Analytics", "Pandas", INT, 200, 1, ("Python",)),
    ("Data Analytics", "Statistics", K, 200, 1, ()),
    ("Data Analytics", "Data Cleaning", INT, 200, 1, ("Pandas",)),
    ("Data Analytics", "Exploratory Data Analysis", INT, 250, 1, ("Data Cleaning", "Statistics")),
    ("Data Analytics", "Data Visualization", C, 200, 1, ("Excel",)),
    ("Data Analytics", "Power BI", INT, 250, 1, ("Excel", "SQL")),
    ("Data Analytics", "Portfolio Projects", R, 300, 2, ("Exploratory Data Analysis", "Power BI")),
    ("Software Engineering", "Programming Fundamentals", INT, 150, 1, ()),
    ("Software Engineering", "Data Structures", INT, 200, 1, ("Programming Fundamentals",)),
    ("Software Engineering", "Algorithms", INT, 250, 1, ("Data Structures",)),
    ("Software Engineering", "Git", INT, 100, 1, ()),
    ("Software Engineering", "GitHub", R, 100, 1, ("Git",)),
    ("Software Engineering", "Databases", INT, 200, 1, ("SQL",)),
    ("Software Engineering", "APIs", INT, 200, 1, ("Programming Fundamentals",)),
    ("Software Engineering", "Testing", INT, 200, 1, ("Programming Fundamentals",)),
    ("Software Engineering", "Backend Development", INT, 300, 1, ("APIs", "Databases")),
    ("Communication", "Written Communication", M, 150, 1, ()),
    ("Communication", "Technical Explanation", M, 200, 1, ("Written Communication",)),
    ("Communication", "Presentations", M, 150, 1, ()),
    ("Communication", "Interview Communication", R, 200, 1, ("Presentations",)),
    ("Personal Finance", "Budgeting", F, 100, 1, ()),
    ("Personal Finance", "Expense Tracking", F, 100, 1, ()),
    ("Personal Finance", "Saving", F, 150, 1, ("Budgeting",)),
    ("Personal Development", "Organization", D, 150, 1, ()),
    ("Personal Development", "Physical Activity", S, 150, 1, ()),
    ("Personal Development", "Sleep Routine Consistency", D, 150, 1, ()),
    ("Personal Development", "Reflection", K, 100, 1, ()),
    ("Personal Development", "Creative Practice", C, 150, 1, ()),
)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:60] or "skill"


def seed_default_skills(conn: Connection, user_id: int, now: str) -> None:
    ids: dict[str, int] = {}
    for tree, name, attribute, xp_required, evidence_required, _ in DEFAULT_SKILLS:
        ids[name] = skills_repo.insert(
            conn,
            user_id,
            {
                "slug": slugify(name),
                "name": name,
                "tree": tree,
                "attribute": attribute,
                "xp_required": xp_required,
                "evidence_required": evidence_required,
                "created_at": now,
            },
        )
    for _, name, _, _, _, prereqs in DEFAULT_SKILLS:
        for prereq in prereqs:
            skills_repo.add_dependency(conn, user_id, ids[name], ids[prereq], now)
