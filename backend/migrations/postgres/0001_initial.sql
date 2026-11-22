-- LIFE.EXE 0001 — MVP schema (PostgreSQL 16 dialect).
-- Semantically identical to migrations/sqlite/0001_initial.sql; differences are
-- only in physical types (identity columns, TIMESTAMPTZ, DATE).
-- Validated by backend/tests/postgres/test_postgres_schema.py against a real server.

CREATE TABLE users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         TEXT        NOT NULL UNIQUE CHECK (email = lower(email) AND length(email) BETWEEN 3 AND 254),
    password_hash TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE sessions (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash   TEXT        NOT NULL UNIQUE,
    created_at   TIMESTAMPTZ NOT NULL,
    expires_at   TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_sessions_user ON sessions(user_id);

CREATE TABLE profiles (
    user_id        BIGINT      PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    display_name   TEXT        NOT NULL CHECK (length(display_name) BETWEEN 1 AND 40),
    title          TEXT        NOT NULL,
    avatar         TEXT        NOT NULL,
    theme          TEXT        NOT NULL DEFAULT 'obsidian',
    timezone       TEXT        NOT NULL,
    day_start_hour SMALLINT    NOT NULL DEFAULT 4 CHECK (day_start_hour BETWEEN 0 AND 6),
    created_at     TIMESTAMPTZ NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL
);

CREATE TABLE skills (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug              TEXT        NOT NULL CHECK (length(slug) BETWEEN 1 AND 60),
    name              TEXT        NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    tree              TEXT        NOT NULL CHECK (length(tree) BETWEEN 1 AND 60),
    attribute         TEXT        NOT NULL CHECK (attribute IN ('INTELLECT','DISCIPLINE','CREATIVITY','STRENGTH','KNOWLEDGE','COMMUNICATION','FINANCIAL_LITERACY','CAREER_DEVELOPMENT')),
    description       TEXT        NOT NULL DEFAULT '' CHECK (length(description) <= 500),
    xp_required       INTEGER     NOT NULL DEFAULT 0 CHECK (xp_required BETWEEN 0 AND 100000),
    evidence_required INTEGER     NOT NULL DEFAULT 1 CHECK (evidence_required BETWEEN 0 AND 50),
    archived_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL,
    UNIQUE (user_id, slug),
    UNIQUE (id, user_id)
);

CREATE TABLE skill_dependencies (
    user_id         BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id        BIGINT      NOT NULL,
    prerequisite_id BIGINT      NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (skill_id, prerequisite_id),
    CHECK (skill_id <> prerequisite_id),
    FOREIGN KEY (skill_id, user_id)        REFERENCES skills(id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (prerequisite_id, user_id) REFERENCES skills(id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_skill_deps_user ON skill_dependencies(user_id);

CREATE TABLE skill_evidence (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id   BIGINT      NOT NULL,
    title      TEXT        NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
    url        TEXT                 CHECK (url IS NULL OR length(url) <= 500),
    notes      TEXT        NOT NULL DEFAULT '' CHECK (length(notes) <= 1000),
    created_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (skill_id, user_id) REFERENCES skills(id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_skill_evidence_user_skill ON skill_evidence(user_id, skill_id);

CREATE TABLE quests (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title               TEXT        NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
    description         TEXT        NOT NULL DEFAULT '' CHECK (length(description) <= 2000),
    category            TEXT        NOT NULL CHECK (category IN ('MAIN','SIDE','DAILY','WEEKLY','MILESTONE','CHALLENGE','BOSS')),
    priority            TEXT        NOT NULL CHECK (priority IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    difficulty          TEXT        NOT NULL CHECK (difficulty IN ('EASY','MEDIUM','HARD','EPIC')),
    status              TEXT        NOT NULL CHECK (status IN ('DRAFT','AVAILABLE','ACTIVE','PAUSED','COMPLETED','CANCELLED','EXPIRED')),
    recurrence          TEXT        NOT NULL DEFAULT 'NONE' CHECK (recurrence IN ('NONE','DAILY','WEEKLY')),
    estimated_minutes   INTEGER     CHECK (estimated_minutes IS NULL OR estimated_minutes BETWEEN 1 AND 1440),
    due_date            DATE,
    completion_criteria TEXT        NOT NULL DEFAULT '' CHECK (length(completion_criteria) <= 500),
    skill_id            BIGINT,
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    archived_at         TIMESTAMPTZ,
    UNIQUE (id, user_id),
    FOREIGN KEY (skill_id, user_id) REFERENCES skills(id, user_id)
);
CREATE INDEX ix_quests_user_status ON quests(user_id, status);
CREATE INDEX ix_quests_user_due    ON quests(user_id, due_date);

CREATE TABLE quest_completions (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quest_id       BIGINT      NOT NULL,
    occurrence_key TEXT        NOT NULL,
    local_date     DATE        NOT NULL,
    completed_at   TIMESTAMPTZ NOT NULL,
    reversed_at    TIMESTAMPTZ,
    FOREIGN KEY (quest_id, user_id) REFERENCES quests(id, user_id)
);
CREATE UNIQUE INDEX ux_quest_completions_live
    ON quest_completions(quest_id, occurrence_key) WHERE reversed_at IS NULL;
CREATE INDEX ix_quest_completions_user_date ON quest_completions(user_id, local_date);

CREATE TABLE xp_events (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount            INTEGER     NOT NULL,
    base_amount       INTEGER     NOT NULL CHECK (base_amount >= 0),
    reason            TEXT        NOT NULL CHECK (reason IN ('QUEST_COMPLETED','QUEST_REOPENED','HABIT_COMPLETED','HABIT_UNDONE','CORRECTION')),
    source_type       TEXT        NOT NULL CHECK (source_type IN ('QUEST_COMPLETION','HABIT_LOG','CORRECTION')),
    source_id         BIGINT,
    skill_id          BIGINT,
    attribute         TEXT        CHECK (attribute IS NULL OR attribute IN ('INTELLECT','DISCIPLINE','CREATIVITY','STRENGTH','KNOWLEDGE','COMMUNICATION','FINANCIAL_LITERACY','CAREER_DEVELOPMENT')),
    idempotency_key   TEXT        NOT NULL,
    reverses_event_id BIGINT      REFERENCES xp_events(id),
    local_date        DATE        NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL,
    UNIQUE (user_id, idempotency_key),
    CHECK ((reverses_event_id IS NULL AND amount >= 0) OR (reverses_event_id IS NOT NULL AND amount <= 0)),
    FOREIGN KEY (skill_id, user_id) REFERENCES skills(id, user_id)
);
CREATE UNIQUE INDEX ux_xp_events_single_reversal ON xp_events(reverses_event_id) WHERE reverses_event_id IS NOT NULL;
CREATE INDEX ix_xp_events_user_date  ON xp_events(user_id, local_date);
CREATE INDEX ix_xp_events_user_skill ON xp_events(user_id, skill_id);

CREATE TABLE habits (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT        NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
    description     TEXT        NOT NULL DEFAULT '' CHECK (length(description) <= 500),
    schedule_kind   TEXT        NOT NULL CHECK (schedule_kind IN ('DAILY','WEEKDAYS','WEEKLY_COUNT')),
    weekdays_mask   SMALLINT    NOT NULL DEFAULT 127 CHECK (weekdays_mask BETWEEN 1 AND 127),
    target_per_week SMALLINT    CHECK (target_per_week IS NULL OR target_per_week BETWEEN 1 AND 7),
    measure         TEXT        NOT NULL CHECK (measure IN ('BOOLEAN','COUNT','DURATION')),
    target_value    INTEGER     NOT NULL DEFAULT 1 CHECK (target_value BETWEEN 1 AND 1440),
    attribute       TEXT        NOT NULL DEFAULT 'DISCIPLINE' CHECK (attribute IN ('INTELLECT','DISCIPLINE','CREATIVITY','STRENGTH','KNOWLEDGE','COMMUNICATION','FINANCIAL_LITERACY','CAREER_DEVELOPMENT')),
    start_date      DATE        NOT NULL,
    archived_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL,
    UNIQUE (id, user_id),
    CHECK (schedule_kind <> 'WEEKLY_COUNT' OR target_per_week IS NOT NULL),
    CHECK (measure <> 'BOOLEAN' OR target_value = 1)
);
CREATE INDEX ix_habits_user ON habits(user_id);

CREATE TABLE habit_pauses (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    habit_id   BIGINT NOT NULL,
    start_date DATE   NOT NULL,
    end_date   DATE,
    CHECK (end_date IS NULL OR end_date >= start_date),
    FOREIGN KEY (habit_id, user_id) REFERENCES habits(id, user_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX ux_habit_pauses_open ON habit_pauses(habit_id) WHERE end_date IS NULL;

CREATE TABLE habit_logs (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    habit_id       BIGINT      NOT NULL,
    local_date     DATE        NOT NULL,
    entry_type     TEXT        NOT NULL CHECK (entry_type IN ('ENTRY','REST')),
    value          INTEGER     NOT NULL DEFAULT 0 CHECK (value BETWEEN 0 AND 1440),
    note           TEXT        NOT NULL DEFAULT '' CHECK (length(note) <= 500),
    award_event_id BIGINT      REFERENCES xp_events(id),
    created_at     TIMESTAMPTZ NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL,
    UNIQUE (habit_id, local_date),
    FOREIGN KEY (habit_id, user_id) REFERENCES habits(id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_habit_logs_user_date ON habit_logs(user_id, local_date);

CREATE TABLE coin_transactions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount          INTEGER     NOT NULL,
    reason          TEXT        NOT NULL CHECK (reason IN ('QUEST_REWARD','QUEST_REWARD_REVERSED','CORRECTION')),
    xp_event_id     BIGINT      REFERENCES xp_events(id),
    idempotency_key TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    UNIQUE (user_id, idempotency_key)
);
CREATE INDEX ix_coin_transactions_user ON coin_transactions(user_id);

CREATE TABLE user_achievements (
    user_id         BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    achievement_key TEXT        NOT NULL,
    unlocked_at     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, achievement_key)
);
