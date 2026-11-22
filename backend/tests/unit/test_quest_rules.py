from datetime import date

import pytest

from lifeexe.core.errors import InvalidTransition
from lifeexe.domain.quests import (
    ONE_OFF_TRANSITIONS,
    RECURRING_TRANSITIONS,
    QuestAction,
    QuestStatus,
    Recurrence,
    allowed_actions,
    is_overdue,
    next_status,
    occurrence_key,
)

S, A = QuestStatus, QuestAction


def test_happy_path_one_off() -> None:
    s = S.DRAFT
    for action, expected in [(A.PUBLISH, S.AVAILABLE), (A.START, S.ACTIVE), (A.COMPLETE, S.COMPLETED)]:
        s = next_status(s, action, Recurrence.NONE)
        assert s is expected


def test_reopen_and_restore() -> None:
    assert next_status(S.COMPLETED, A.REOPEN, Recurrence.NONE) is S.ACTIVE
    assert next_status(S.CANCELLED, A.RESTORE, Recurrence.NONE) is S.AVAILABLE
    assert next_status(S.EXPIRED, A.RESTORE, Recurrence.NONE) is S.AVAILABLE


@pytest.mark.parametrize("status", list(S))
@pytest.mark.parametrize("action", list(A))
def test_every_pair_is_either_defined_or_rejected(status: QuestStatus, action: QuestAction) -> None:
    key = (status, action)
    if key in ONE_OFF_TRANSITIONS:
        assert next_status(status, action, Recurrence.NONE) is ONE_OFF_TRANSITIONS[key]
    else:
        with pytest.raises(InvalidTransition):
            next_status(status, action, Recurrence.NONE)


@pytest.mark.parametrize("status", [S.DRAFT, S.AVAILABLE, S.PAUSED, S.COMPLETED, S.CANCELLED, S.EXPIRED])
def test_complete_only_from_active(status: QuestStatus) -> None:
    with pytest.raises(InvalidTransition):
        next_status(status, A.COMPLETE, Recurrence.NONE)


def test_recurring_complete_keeps_active() -> None:
    assert next_status(S.ACTIVE, A.COMPLETE, Recurrence.DAILY) is S.ACTIVE
    assert next_status(S.ACTIVE, A.REOPEN, Recurrence.WEEKLY) is S.ACTIVE
    assert (S.ACTIVE, A.EXPIRE) not in RECURRING_TRANSITIONS
    assert (S.COMPLETED, A.REOPEN) not in RECURRING_TRANSITIONS


def test_allowed_actions_one_off() -> None:
    assert allowed_actions(S.AVAILABLE, Recurrence.NONE, False) == [A.START, A.CANCEL, A.EXPIRE]
    assert allowed_actions(S.ACTIVE, Recurrence.NONE, False) == [A.PAUSE, A.COMPLETE, A.CANCEL, A.EXPIRE]
    assert allowed_actions(S.COMPLETED, Recurrence.NONE, True) == [A.REOPEN]


def test_allowed_actions_recurring_depend_on_occurrence() -> None:
    assert A.COMPLETE in allowed_actions(S.ACTIVE, Recurrence.DAILY, occurrence_completed=False)
    assert A.REOPEN not in allowed_actions(S.ACTIVE, Recurrence.DAILY, occurrence_completed=False)
    done = allowed_actions(S.ACTIVE, Recurrence.DAILY, occurrence_completed=True)
    assert A.REOPEN in done and A.COMPLETE not in done


def test_occurrence_keys() -> None:
    d = date(2026, 11, 22)
    assert occurrence_key(Recurrence.NONE, d) == "once"
    assert occurrence_key(Recurrence.DAILY, d) == "2026-11-22"
    assert occurrence_key(Recurrence.WEEKLY, d) == "2026-W47"


def test_weekly_key_across_year_boundary() -> None:
    # ISO weeks: 2026 has 53 weeks; Fri 1 Jan 2027 still belongs to 2026-W53.
    assert occurrence_key(Recurrence.WEEKLY, date(2026, 12, 31)) == "2026-W53"
    assert occurrence_key(Recurrence.WEEKLY, date(2027, 1, 1)) == "2026-W53"
    assert occurrence_key(Recurrence.WEEKLY, date(2027, 1, 4)) == "2027-W01"


def test_overdue_is_derived_and_ignores_terminal() -> None:
    today = date(2026, 11, 22)
    assert is_overdue(S.ACTIVE, date(2026, 11, 21), today)
    assert not is_overdue(S.ACTIVE, today, today)
    assert not is_overdue(S.COMPLETED, date(2026, 1, 1), today)
    assert not is_overdue(S.ACTIVE, None, today)
