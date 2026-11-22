"""Quest lifecycle rules (pure, no I/O).

One-off quests:
    DRAFT -> AVAILABLE -> ACTIVE -> COMPLETED
    ACTIVE <-> PAUSED
    DRAFT/AVAILABLE/ACTIVE/PAUSED -> CANCELLED
    AVAILABLE/ACTIVE/PAUSED -> EXPIRED            (explicit; never automatic)
    COMPLETED -> ACTIVE                            (reopen: XP is reversed)
    CANCELLED/EXPIRED -> AVAILABLE                 (restore)

Recurring quests (DAILY / WEEKLY) stay ACTIVE while running. "Complete" records
one completion for the *current occurrence* (a local date or ISO week) and the
quest stays ACTIVE; "reopen" undoes the current occurrence's completion.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from lifeexe.core.errors import InvalidTransition


class QuestStatus(StrEnum):
    DRAFT = "DRAFT"
    AVAILABLE = "AVAILABLE"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class QuestAction(StrEnum):
    PUBLISH = "publish"
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    COMPLETE = "complete"
    REOPEN = "reopen"
    CANCEL = "cancel"
    EXPIRE = "expire"
    RESTORE = "restore"


class QuestCategory(StrEnum):
    MAIN = "MAIN"
    SIDE = "SIDE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MILESTONE = "MILESTONE"
    CHALLENGE = "CHALLENGE"
    BOSS = "BOSS"


class Priority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


PRIORITY_RANK: dict[Priority, int] = {
    Priority.LOW: 1,
    Priority.MEDIUM: 2,
    Priority.HIGH: 3,
    Priority.CRITICAL: 4,
}


class Recurrence(StrEnum):
    NONE = "NONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


S = QuestStatus
A = QuestAction

#: (current status, action) -> next status, for one-off quests.
ONE_OFF_TRANSITIONS: dict[tuple[QuestStatus, QuestAction], QuestStatus] = {
    (S.DRAFT, A.PUBLISH): S.AVAILABLE,
    (S.DRAFT, A.CANCEL): S.CANCELLED,
    (S.AVAILABLE, A.START): S.ACTIVE,
    (S.AVAILABLE, A.CANCEL): S.CANCELLED,
    (S.AVAILABLE, A.EXPIRE): S.EXPIRED,
    (S.ACTIVE, A.PAUSE): S.PAUSED,
    (S.ACTIVE, A.COMPLETE): S.COMPLETED,
    (S.ACTIVE, A.CANCEL): S.CANCELLED,
    (S.ACTIVE, A.EXPIRE): S.EXPIRED,
    (S.PAUSED, A.RESUME): S.ACTIVE,
    (S.PAUSED, A.CANCEL): S.CANCELLED,
    (S.PAUSED, A.EXPIRE): S.EXPIRED,
    (S.COMPLETED, A.REOPEN): S.ACTIVE,
    (S.CANCELLED, A.RESTORE): S.AVAILABLE,
    (S.EXPIRED, A.RESTORE): S.AVAILABLE,
}

#: For recurring quests COMPLETE/REOPEN act on the current occurrence and keep
#: the quest ACTIVE; EXPIRE is not meaningful (there is no single due date).
RECURRING_TRANSITIONS: dict[tuple[QuestStatus, QuestAction], QuestStatus] = {
    **{k: v for k, v in ONE_OFF_TRANSITIONS.items() if k[1] not in (A.COMPLETE, A.REOPEN, A.EXPIRE)},
    (S.ACTIVE, A.COMPLETE): S.ACTIVE,
    (S.ACTIVE, A.REOPEN): S.ACTIVE,
}

TERMINAL_STATUSES = frozenset({S.COMPLETED, S.CANCELLED, S.EXPIRED})
EDITABLE_STATUSES = frozenset({S.DRAFT, S.AVAILABLE, S.ACTIVE, S.PAUSED})


def _table(recurrence: Recurrence) -> dict[tuple[QuestStatus, QuestAction], QuestStatus]:
    return ONE_OFF_TRANSITIONS if recurrence is Recurrence.NONE else RECURRING_TRANSITIONS


def next_status(status: QuestStatus, action: QuestAction, recurrence: Recurrence) -> QuestStatus:
    try:
        return _table(recurrence)[(status, action)]
    except KeyError:
        raise InvalidTransition(f"Cannot {action.value} a quest that is {status.value}.") from None


def allowed_actions(
    status: QuestStatus, recurrence: Recurrence, occurrence_completed: bool
) -> list[QuestAction]:
    """Actions the UI may offer. The UI never re-implements the state machine."""
    actions = [a for (s, a) in _table(recurrence) if s is status]
    if recurrence is not Recurrence.NONE and status is S.ACTIVE:
        drop = A.COMPLETE if occurrence_completed else A.REOPEN
        actions = [a for a in actions if a is not drop]
    order = list(QuestAction)
    return sorted(set(actions), key=order.index)


def occurrence_key(recurrence: Recurrence, local_day: date) -> str:
    """Stable identifier of the occurrence a completion belongs to.

    One-off quests have a single occurrence. Daily quests use the user's local
    date (after their day-boundary shift). Weekly quests use the ISO week.
    """
    if recurrence is Recurrence.NONE:
        return "once"
    if recurrence is Recurrence.DAILY:
        return local_day.isoformat()
    iso = local_day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def is_overdue(status: QuestStatus, due: date | None, today: date) -> bool:
    """Derived display flag. Overdue quests are never auto-expired or penalised."""
    return due is not None and due < today and status not in TERMINAL_STATUSES
