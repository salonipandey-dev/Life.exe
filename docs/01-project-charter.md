# 01 Project charter, feasibility and plan

| | |
|---|---|
| Project | LIFE.EXE: "Level up your reality" |
| Owner | Saloni Pandey |
| Product type | Full-stack web app (desktop-first, responsive, installable PWA manifest) |
| Version covered | 0.1.0 (MVP foundation and first vertical slice) |
| Last updated | 2026-11-22 |

## 1. Problem statement
Students and early-career developers juggle study, projects, job applications, habits and health in separate tools: a to-do app, a habit tracker, a spreadsheet, a notes app. None of them connects effort to visible progress, and most gamified apps reward streak-anxiety or meaningless taps. The result is either low motivation or unhealthy pressure.

LIFE.EXE combines planning, habit tracking, skill progression and honest analytics in one personal operating system, using RPG progression (XP, levels, skills, achievements) that is earned only from recorded, meaningful actions, never punishes rest, and is fully explainable.

## 2. Objectives and success measures
| Objective | Measure for v1.0 |
|---|---|
| Make daily planning fast | Create and complete a quest in under 15 seconds from the Command Center |
| Trustworthy progression | 0 duplicate-reward defects; every XP point traceable to a ledger row |
| Healthy motivation | No mechanic removes XP or lowers an attribute for a missed day |
| Real analytics | Every displayed metric has a written definition and is backed by tests |
| Interview-ready engineering | Architecture, schema, algorithms and tests documented and reproducible |

## 3. Stakeholders
| Stakeholder | Interest | Influence | Engagement |
|---|---|---|---|
| Saloni Pandey (owner, primary user) | A tool she uses daily; a portfolio project she can defend in interviews | High | Decides scope and priorities; acceptance testing |
| Future users (students, self-learners) | Reliable, private, motivating app | Medium | Persona-driven requirements |
| Recruiters and interviewers | Evidence of engineering judgement | Medium | Docs, ADRs, test reports, demo |
| Hosting providers | Terms of service, cost | Low | Chosen at deployment time |

## 4. Personas
**Saloni, B.Tech CSE student and aspiring data analyst.** Studies SQL, Python, Excel and Power BI, practises DSA in Java, applies for internships. Works late; a 1 a.m. study session should count for "today". Wants to see which skills she has actually *demonstrated* versus only practised.

**Arjun, self-taught developer with a day job.** Two evenings a week for learning; needs weekly-count habits (3x/week), not daily guilt. Values export and privacy.

**Meera, early-career analyst.** Uses it for career tracking and finance later; cares about analytics accuracy and wants to review her week without judgement.

## 5. Alternatives assessment
| Product | Strength | Gap LIFE.EXE addresses |
|---|---|---|
| Habitica | Strong RPG loop | Punishes missed dailies (HP loss); no skill evidence or analytics depth |
| Todoist / TickTick | Excellent task management | No progression model or skill tracking |
| Notion templates | Flexible | Manual, no enforced rules, no integrity guarantees |
| Loop / Streaks | Simple habit streaks | No quests, skills, or cross-domain analytics |

## 6. Feasibility
- **Technical: feasible.** Proven stack. Constraint found during the audit: no package installation in the build environment, so FastAPI/SQLAlchemy/Vite/etc. were replaced by installed equivalents (ADR-002, ADR-003, ADR-004). PostgreSQL 16 server was available to validate the target schema.
- **Operational: feasible.** Single process plus one SQLite file today; a backup is one file copy. No on-call burden for a personal app.
- **Economic: feasible.** Runs on any small VM or free-tier platform with a persistent disk; no paid dependencies. AI features (v2.5) would add per-call costs and remain optional.
- **Legal and privacy.** Personal data (email, habits, later finance and wellness) requires: password hashing, account-level authorization, export and deletion (implemented), no sending data to third parties or AI providers without explicit consent, cookie-only session (no tracking). India's DPDP Act 2023 principles (purpose limitation, consent, erasure) are reflected in the privacy design; a formal legal review is out of scope.

## 7. Scope
**In scope for the MVP (v1.0):** authentication, player profile, quest CRUD and lifecycle, transactional XP with idempotency, deterministic leveling, skills with prerequisite graph and evidence, habits with streaks, Command Center, basic analytics, achievements (minimal), settings, data export and deletion, essential tests.

**Out of scope until later releases:** study timer and spaced repetition, goals and roadmaps, projects, career tracker, finance, wellness, reward shop, daily-planning algorithm, AI insights, integrations (GitHub, calendar, wearables), SONIC.EXE visualiser integration.

## 8. Work breakdown structure
```
LIFE.EXE v1.0
├─ 1 Foundation ............ repo, tooling, config, migrations, CI, docs skeleton      [done]
├─ 2 Identity & character .. register/login/logout, sessions, profile, leveling        [done]
├─ 3 Quests ................ CRUD, lifecycle, completion, ledger, idempotency, history [done]
├─ 4 Command Center ........ priorities, today, habits, week summary, quick add        [done]
├─ 5 Habits & skills ....... schedules, logs, streaks, pauses; skill DAG, evidence     [done]
├─ 6 Analytics ............. series, heatmap, attributes, insights, definitions        [done]
├─ 7 Achievements & settings catalog, idempotent awards; profile, tz, export, delete  [done]
└─ 8 Stabilisation ......... a11y audit, PostgreSQL driver, deployment, docs           [partly done]
```

## 9. Milestone plan
| Milestone | Content | Status |
|---|---|---|
| M0 Sprint 0 | Audit, structure, tooling, migrations, ADRs | Done |
| M1 Identity | Auth, profile, leveling engine | Done |
| M2 Quest slice | Create -> start -> complete -> ledger -> level -> display, with tests | Done |
| M3 Command Center | Dashboard API and UI | Done |
| M4 Habits & skills | Streak engine, skill graph | Done |
| M5 Analytics | Metrics, charts, insights | Done |
| M6 Stabilisation | PostgreSQL driver, deployment, manual a11y audit, real React typecheck | Open |
| v1.5 | Study tracker, projects, career tracker, weekly review | Planned |

## 10. MVP acceptance criteria
1. A new user can register, sign in, sign out; sessions expire and are revocable. **Met** (integration + E2E).
2. Creating, starting and completing a quest awards XP exactly once per occurrence, even under concurrent requests. **Met** (12-thread test).
3. Level is computed by `round(100*(L-1)^1.5)` and shown with progress to the next level. **Met.**
4. Reopening a quest reverses its XP through a ledger entry. **Met.**
5. Habits track daily, specific-day and N-per-week schedules with streaks that respect rest days, pauses, time zones and the day-start hour. **Met.**
6. Skills form an acyclic graph; cycles are rejected; a skill needs XP *and* evidence. **Met.**
7. Analytics show net XP per day, activity, attribute and skill distribution, with definitions; insights appear only with supporting data. **Met.**
8. No user can read or modify another user's data. **Met** (isolation suite).
9. Users can export and permanently delete their data. **Met.**
10. Deployed to a public HTTPS URL. **Not met:** deployment is prepared (Dockerfile, guide) but not performed or verified.

## 11. Risk register
| ID | Risk | Likelihood | Impact | Mitigation | Status |
|---|---|---|---|---|---|
| R1 | Duplicate rewards via retries or races | Medium | High | Ledger idempotency keys, partial unique index, `BEGIN IMMEDIATE`, concurrency tests | Mitigated |
| R2 | Day-boundary bugs (time zones, DST, late nights) | High | Medium | Local-date stored per event; DST tests; alias normalisation (D-001) | Mitigated |
| R3 | Scope creep across 15 modules | High | High | MVP-first plan; later modules not scaffolded | Controlled |
| R4 | Dependency substitutions diverge from the recommended stack | Medium | Medium | ADRs, pure domain layer, migration paths documented | Accepted |
| R5 | SQLite single-writer limits | Low (single user) | Medium | PostgreSQL schema validated; driver swap planned | Accepted |
| R6 | Gamification encourages overwork | Medium | High | Daily XP cap, no penalties, rest days, neutral copy | Mitigated |
| R7 | Personal data exposure | Low | High | Authorization on every query, composite FKs, CSP, HttpOnly cookies, export/delete | Mitigated |
| R8 | Untested deployment surprises | Medium | Medium | Dockerfile + guide; verify on first deploy | Open |
| R9 | JSX typing weaker without @types/react | Medium | Low | E2E coverage; run real typecheck when packages install | Open |
