"""Request and response schemas (Pydantic v2).

Request models use ``extra="forbid"``: a client that sends ``xp``,
``total_xp``, ``coins`` or any other unknown field gets a 422, so progression
values can only ever originate on the server.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lifeexe.core.timeutil import normalize_timezone
from lifeexe.domain.habits import Measure, ScheduleKind
from lifeexe.domain.quests import Priority, QuestCategory, Recurrence
from lifeexe.domain.rewards import Attribute, Difficulty

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


class In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Out(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# --- auth -----------------------------------------------------------------------


def _email(v: str) -> str:
    v = v.strip().lower()
    if len(v) > 254 or not EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address.")
    return v


class RegisterIn(In):
    email: str
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=40)
    timezone: str = "UTC"

    @field_validator("email")
    @classmethod
    def _norm_email(cls, v: str) -> str:
        return _email(v)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        canonical = normalize_timezone(v)
        if canonical is None:
            raise ValueError("Unknown time zone.")
        return canonical


class LoginIn(In):
    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _norm_email(cls, v: str) -> str:
        return _email(v)


class SessionOut(Out):
    user_id: int
    expires_at: str


# --- progress / profile -----------------------------------------------------------


class ProgressOut(Out):
    level: int
    total_xp: int
    level_floor_xp: int
    next_level_xp: int
    xp_into_level: int
    xp_span: int
    xp_to_next_level: int
    progress_ratio: float


class AttributeOut(Out):
    attribute: str
    xp: int
    rank: int


class TitleOption(Out):
    title: str
    unlock_level: int
    unlocked: bool


class ProfileOptions(Out):
    titles: list[TitleOption]
    unlocked_titles: list[str]
    avatars: list[str]
    themes: list[str]


class ProfileOut(Out):
    user_id: int
    today: str
    email: str
    display_name: str
    title: str
    avatar: str
    theme: str
    timezone: str
    day_start_hour: int
    account_created_at: str
    progress: ProgressOut
    coins: int
    attributes: list[AttributeOut]
    options: ProfileOptions
    game: dict[str, Any]


class ProfileUpdateIn(In):
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    title: str | None = Field(default=None, max_length=40)
    avatar: str | None = Field(default=None, max_length=20)
    theme: str | None = Field(default=None, max_length=20)
    timezone: str | None = Field(default=None, max_length=64)
    day_start_hour: int | None = Field(default=None, ge=0, le=6)


class PasswordChangeIn(In):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class DeleteAccountIn(In):
    password: str = Field(min_length=1, max_length=128)
    confirm: Literal["DELETE"]


# --- quests ---------------------------------------------------------------------


class SkillRef(Out):
    id: int
    name: str
    attribute: str


class QuestCreateIn(In):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    category: QuestCategory = QuestCategory.SIDE
    priority: Priority = Priority.MEDIUM
    difficulty: Difficulty = Difficulty.MEDIUM
    recurrence: Recurrence = Recurrence.NONE
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    due_date: date | None = None
    completion_criteria: str = Field(default="", max_length=500)
    skill_id: int | None = Field(default=None, ge=1)
    as_draft: bool = False


class QuestUpdateIn(In):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    category: QuestCategory | None = None
    priority: Priority | None = None
    difficulty: Difficulty | None = None
    recurrence: Recurrence | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    due_date: date | None = None
    completion_criteria: str | None = Field(default=None, max_length=500)
    skill_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _no_null_required(self) -> QuestUpdateIn:
        for name in ("title", "description", "category", "priority", "difficulty", "recurrence", "completion_criteria"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class QuestHistoryItem(Out):
    id: int
    occurrence_key: str
    local_date: str
    completed_at: str
    reversed_at: str | None
    xp_awarded: int


class QuestOut(Out):
    id: int
    title: str
    description: str
    category: str
    priority: str
    difficulty: str
    status: str
    recurrence: str
    estimated_minutes: int | None
    due_date: str | None
    completion_criteria: str
    skill: SkillRef | None
    xp_reward: int
    coin_reward: int
    occurrence_completed: bool
    completion_count: int
    overdue: bool
    archived: bool
    allowed_actions: list[str]
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None
    history: list[QuestHistoryItem] | None = None


class QuestListOut(Out):
    items: list[QuestOut]
    total: int
    limit: int
    offset: int


class QuestListQuery(In):
    status: str | None = None  # comma-separated
    category: QuestCategory | None = None
    difficulty: Difficulty | None = None
    q: str | None = Field(default=None, max_length=100)
    include_archived: bool = False
    sort: Literal["created_at", "-created_at", "due_date", "-due_date", "priority", "-priority", "title"] = "-priority"
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=100_000)

    @field_validator("status")
    @classmethod
    def _statuses(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        allowed = {"DRAFT", "AVAILABLE", "ACTIVE", "PAUSED", "COMPLETED", "CANCELLED", "EXPIRED"}
        parts = [p.strip().upper() for p in v.split(",") if p.strip()]
        bad = [p for p in parts if p not in allowed]
        if bad:
            raise ValueError(f"unknown status: {', '.join(bad)}")
        return ",".join(parts)


class AchievementBrief(Out):
    key: str
    title: str
    description: str


class RewardOut(Out):
    xp_awarded: int
    base_xp: int
    coins_awarded: int
    capped: bool
    daily_cap: int
    occurrence_key: str


class CompletionOut(Out):
    quest: QuestOut
    reward: RewardOut
    progress: ProgressOut
    level_before: int
    leveled_up: bool
    achievements_unlocked: list[AchievementBrief]


class ReopenOut(Out):
    quest: QuestOut
    xp_reversed: int
    progress: ProgressOut
    level_before: int


# --- habits ---------------------------------------------------------------------


class HabitCreateIn(In):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    schedule_kind: ScheduleKind = ScheduleKind.DAILY
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)), min_length=1, max_length=7)
    target_per_week: int | None = Field(default=None, ge=1, le=7)
    measure: Measure = Measure.BOOLEAN
    target_value: int = Field(default=1, ge=1, le=1440)
    attribute: Attribute = Attribute.DISCIPLINE

    @model_validator(mode="after")
    def _consistent(self) -> HabitCreateIn:
        if any(d < 0 or d > 6 for d in self.weekdays) or len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("weekdays must be distinct values 0 (Mon) .. 6 (Sun)")
        if self.schedule_kind is ScheduleKind.WEEKLY_COUNT and self.target_per_week is None:
            raise ValueError("weekly-count habits need target_per_week")
        if self.measure is Measure.BOOLEAN:
            self.target_value = 1
        return self


class HabitUpdateIn(In):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    schedule_kind: ScheduleKind | None = None
    weekdays: list[int] | None = Field(default=None, min_length=1, max_length=7)
    target_per_week: int | None = Field(default=None, ge=1, le=7)
    measure: Measure | None = None
    target_value: int | None = Field(default=None, ge=1, le=1440)
    attribute: Attribute | None = None


class HabitLogIn(In):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)
    day: date | None = Field(default=None, alias="date")
    entry_type: Literal["ENTRY", "REST"] = "ENTRY"
    value: int | None = Field(default=None, ge=0, le=1440)
    note: str = Field(default="", max_length=500)


class HabitOut(Out):
    id: int
    name: str
    description: str
    schedule_kind: str
    weekdays: list[int]
    target_per_week: int | None
    measure: str
    target_value: int
    attribute: str
    start_date: str
    archived: bool
    paused: bool
    scheduled_today: bool
    today: dict[str, Any]
    stats: dict[str, Any]
    calendar: list[dict[str, Any]]


class HabitListOut(Out):
    items: list[HabitOut]
    today: str


class HabitLogOut(Out):
    habit: HabitOut
    xp_delta: int
    progress: ProgressOut
    achievements_unlocked: list[AchievementBrief]


class IncludeArchivedQuery(In):
    include_archived: bool = False


# --- skills ---------------------------------------------------------------------


class SkillCreateIn(In):
    name: str = Field(min_length=1, max_length=60)
    tree: str = Field(min_length=1, max_length=60)
    attribute: Attribute = Attribute.INTELLECT
    description: str = Field(default="", max_length=500)
    xp_required: int = Field(default=150, ge=0, le=100_000)
    evidence_required: int = Field(default=1, ge=0, le=50)


class SkillUpdateIn(In):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    tree: str | None = Field(default=None, min_length=1, max_length=60)
    attribute: Attribute | None = None
    description: str | None = Field(default=None, max_length=500)
    xp_required: int | None = Field(default=None, ge=0, le=100_000)
    evidence_required: int | None = Field(default=None, ge=0, le=50)


class DependencyIn(In):
    prerequisite_id: int = Field(ge=1)


class EvidenceIn(In):
    title: str = Field(min_length=1, max_length=120)
    url: str | None = Field(default=None, max_length=500)
    notes: str = Field(default="", max_length=1000)

    @field_validator("url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if not re.match(r"^https?://[^\s]+$", v):
            raise ValueError("URL must start with http:// or https://")
        return v


class SkillOut(Out):
    id: int
    slug: str
    name: str
    tree: str
    attribute: str
    description: str
    xp: int
    xp_required: int
    evidence_count: int
    evidence_required: int
    status: str
    prerequisite_ids: list[int]
    tier: int
    roadmap_position: int


class EvidenceOut(Out):
    id: int
    title: str
    url: str | None
    notes: str
    created_at: str


class SkillDetailOut(SkillOut):
    evidence: list[EvidenceOut]
    achievements_unlocked: list[AchievementBrief] = []


class SkillListOut(Out):
    skills: list[SkillOut]
    trees: list[str]


# --- analytics / dashboard / achievements -------------------------------------------


class AnalyticsQuery(In):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    from_: date | None = Field(default=None, alias="from")
    to: date | None = None


class AnalyticsOut(Out):
    range: dict[str, Any]
    totals: dict[str, int]
    series: dict[str, list[dict[str, Any]]]
    xp_by_attribute: list[dict[str, Any]]
    xp_by_skill: list[dict[str, Any]]
    completions_by_category: list[dict[str, Any]]
    weekly: dict[str, Any]
    insights: list[dict[str, Any]]
    definitions: dict[str, str]


class DashboardOut(Out):
    today: str
    character: dict[str, Any]
    priorities: list[QuestOut]
    today_quests: list[QuestOut]
    habits: list[HabitOut]
    week: dict[str, int | str]
    recent_achievements: list[dict[str, Any]]
    recent_xp: list[dict[str, Any]]


class AchievementGalleryOut(Out):
    achievements: list[dict[str, Any]]
    unlocked_count: int
    total: int


class HealthOut(Out):
    status: str
    database: str
    version: str
