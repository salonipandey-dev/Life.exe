# 04 System architecture

LIFE.EXE is a **modular monolith** (ADR-001): one backend process serves the JSON API and the built single-page app from the same origin. Business rules live in a pure domain layer that has no I/O.

## 1. Context
```mermaid
flowchart LR
  user([Player<br/>browser or installed PWA])
  subgraph LIFEEXE [LIFE.EXE]
    app[Backend + SPA<br/>Starlette / React]
    db[(SQLite file<br/>PostgreSQL-ready schema)]
  end
  user -- HTTPS, session cookie --> app
  app --> db
  future[(Future, opt-in only:<br/>GitHub, calendar, AI provider)]
  app -. not implemented .-> future
```
No third-party service receives personal data in v0.1.

## 2. Containers
```mermaid
flowchart TB
  subgraph Browser
    spa[React 19 SPA<br/>hash router, query cache,<br/>SVG charts]
  end
  subgraph Server [Python 3.13 process - uvicorn, 1 worker]
    mw[ASGI middleware<br/>security headers, request id, JSON logs]
    api[API layer<br/>routing.py: validation, auth, CSRF,<br/>rate limit, OpenAPI]
    svc[Application services<br/>one transaction per use case]
    dom[Domain rules<br/>leveling, rewards, quest FSM,<br/>streaks, skill DAG, insights]
    repo[Repositories<br/>parameterised SQL]
    static[Static files<br/>index.html, assets, fonts]
  end
  dbase[(SQLite WAL)]
  spa -- "/api/v1/* JSON" --> mw --> api --> svc
  svc --> dom
  svc --> repo --> dbase
  spa -- "/, /assets, /fonts" --> static
```

## 3. Backend components
```mermaid
flowchart LR
  subgraph api [lifeexe.api]
    routes[routes/*: auth, quests, habits,<br/>skills, account, views]
    schemas[schemas.py]
    routing[routing.py]
  end
  subgraph services [lifeexe.services]
    auth[AuthService]
    quests[QuestService]
    habits[HabitService]
    skills[SkillService]
    analytics[AnalyticsService]
    profile[ProfileService<br/>dashboard, export, delete]
    ach[evaluate_achievements]
  end
  subgraph domain [lifeexe.domain - pure]
    leveling
    rewards
    qrules[quests]
    hrules[habits]
    srules[skills]
    arules[analytics]
    achdef[achievements]
  end
  subgraph repos [lifeexe.repositories]
    r_users[users]
    r_quests[quests]
    r_ledger[ledger]
    r_habits[habits]
    r_skills[skills]
    r_an[analytics]
  end
  routes --> schemas
  routes --> services
  quests --> qrules & rewards & leveling & ach
  habits --> hrules & rewards
  skills --> srules
  analytics --> arules
  ach --> achdef
  services --> repos
```
Dependency rule: `api -> services -> {domain, repositories}`; `domain` imports nothing from the other layers except the error types in `core/errors.py`.

## 4. Domain model
```mermaid
classDiagram
  class User { email; password_hash }
  class Profile { display_name; title; avatar; theme; timezone; day_start_hour }
  class Quest { title; category; priority; difficulty; status; recurrence; due_date }
  class QuestCompletion { occurrence_key; local_date; reversed_at }
  class XpEvent { amount; reason; idempotency_key; local_date; reverses_event_id }
  class CoinTransaction { amount; reason }
  class Habit { schedule_kind; weekdays; target_per_week; measure; target_value }
  class HabitLog { local_date; entry_type; value }
  class Skill { name; tree; attribute; xp_required; evidence_required }
  class SkillEvidence { title; url }
  User "1" -- "1" Profile
  User "1" -- "*" Quest
  Quest "1" -- "*" QuestCompletion
  QuestCompletion "1" -- "1..2" XpEvent : award + optional reversal
  XpEvent "1" -- "0..1" CoinTransaction
  User "1" -- "*" Habit
  Habit "1" -- "*" HabitLog
  HabitLog "1" -- "0..*" XpEvent
  User "1" -- "*" Skill
  Skill "*" -- "*" Skill : prerequisite (DAG)
  Skill "1" -- "*" SkillEvidence
  Quest "*" -- "0..1" Skill : trains
```

## 5. Quest state machine
```mermaid
stateDiagram-v2
  [*] --> DRAFT : create (as draft)
  [*] --> AVAILABLE : create
  DRAFT --> AVAILABLE : publish
  DRAFT --> CANCELLED : cancel
  AVAILABLE --> ACTIVE : start
  AVAILABLE --> CANCELLED : cancel
  AVAILABLE --> EXPIRED : expire
  ACTIVE --> PAUSED : pause
  PAUSED --> ACTIVE : resume
  ACTIVE --> COMPLETED : complete (awards XP once)
  ACTIVE --> CANCELLED : cancel
  ACTIVE --> EXPIRED : expire
  PAUSED --> CANCELLED : cancel
  PAUSED --> EXPIRED : expire
  COMPLETED --> ACTIVE : reopen (reverses XP)
  CANCELLED --> AVAILABLE : restore
  EXPIRED --> AVAILABLE : restore
```
Recurring quests stay `ACTIVE`; *complete* and *reopen* act on the current occurrence (local date or ISO week) and keep the status. `EXPIRED` is never set automatically.

## 6. Sequence: completing a quest (the first vertical slice)
```mermaid
sequenceDiagram
  autonumber
  participant UI as React UI
  participant API as routing.py
  participant S as QuestService
  participant D as domain
  participant DB as SQLite
  UI->>API: POST /api/v1/quests/42/complete (cookie, X-LifeExe-CSRF)
  API->>API: CSRF + Origin check, authenticate session
  API->>S: complete(user, 42)
  S->>DB: BEGIN IMMEDIATE (write lock)
  S->>DB: load profile (local date) and quest (user-scoped)
  S->>D: next_status(ACTIVE, complete), occurrence_key(...)
  S->>DB: live completion for occurrence? (yes -> 409, rollback)
  S->>DB: INSERT quest_completions (partial unique index)
  S->>D: capped_reward(base XP, net XP today)
  S->>DB: INSERT xp_events (idempotency key) + coin_transactions
  S->>DB: UPDATE quest status, evaluate achievements (ON CONFLICT DO NOTHING)
  S->>DB: COMMIT
  S-->>API: quest, reward, progress, leveled_up, achievements
  API-->>UI: 200 JSON (validated by CompletionOut)
  UI->>UI: toast, invalidate dashboard/quests/profile/analytics
```

## 7. Authentication flow
```mermaid
sequenceDiagram
  participant B as Browser
  participant A as API
  participant DB as Database
  B->>A: POST /auth/login {email, password}
  A->>A: rate limit per IP, then scrypt verify (dummy hash if email unknown)
  A->>DB: INSERT sessions (sha256(token), expires_at)
  A-->>B: Set-Cookie lifeexe_session (HttpOnly, SameSite=Lax, Secure in prod)
  B->>A: GET /api/v1/dashboard (cookie)
  A->>DB: SELECT session by sha256(token), check expiry
  A-->>B: 200 or 401
  B->>A: POST /auth/logout (X-LifeExe-CSRF)
  A->>DB: DELETE session
  A-->>B: 204 + cookie cleared
```

## 8. Analytics data flow
```mermaid
flowchart LR
  ev[Raw events<br/>quest_completions, habit_logs, xp_events<br/>each with local_date] --> val[Validation<br/>at write time: schemas,<br/>constraints, idempotency]
  val --> agg[Aggregation on request<br/>GROUP BY local_date / attribute / skill<br/>reversed rows excluded or netted]
  agg --> met[Metrics + dense daily series<br/>domain/analytics.py]
  met --> ins[Insights<br/>only with data, with basis]
  met --> viz[SVG charts + table view]
```
Derived statistics are never stored, so they cannot drift from the raw events.

## 9. Frontend structure
```
frontend/src
├─ main.tsx, app/App.tsx         auth gate, routing, theme
├─ lib/                          api client (CSRF), query cache, router, format, types (pure, unit-tested)
├─ components/                   Shell, Sigil, quests, habits, charts, Dialog, feedback (toasts/states)
└─ pages/                        AuthPage, CommandCenter, QuestBoard, HabitsPage, SkillsPage,
                                 AnalyticsPage, AchievementsPage, SettingsPage
```
The UI holds no game rules: it renders `allowed_actions`, `progress`, `stats` and statuses computed by the server.

## 10. Deployment architecture (target)
```mermaid
flowchart LR
  u([User]) -- HTTPS --> proxy[TLS-terminating platform proxy]
  proxy --> c[Container: python -m lifeexe<br/>serves API + SPA]
  c --> vol[(Persistent volume<br/>/data/lifeexe.db)]
  c -. nightly .-> bak[(Backup copy<br/>sqlite3 .backup)]
```
One container is enough for a personal deployment. Moving to managed PostgreSQL changes only the database box (ADR-003). See `12-deployment.md`.
