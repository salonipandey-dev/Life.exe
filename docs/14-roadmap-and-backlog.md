# 14 Roadmap and product backlog

## Roadmap
| Release | Theme | Contents | Status |
|---|---|---|---|
| v0.1 (this checkpoint) | Core OS foundation | Auth, profile, quests + ledger + leveling, habits, skills, Command Center, analytics, achievements, settings, export/delete | **Built and tested, not deployed** |
| v1.0 | MVP live | PostgreSQL driver, deployment, axe audit, real React typecheck, password reset (needs email), dependency scanning | Next |
| v1.5 | Learning & career | Study sessions + focus timer (tab-safe, no idle rewards), learning paths, project tracker, job application tracker with CSV import, weekly review, daily planner | Planned |
| v2.0 | Life management | Finance (integer minor units, INR default, budgets, savings rate), wellness (optional, private, no calorie restriction), goals and milestones, reward shop (cosmetic, no gambling), boss quests | Planned |
| v2.5 | Intelligence | Evidence-based insights, skill-gap analysis vs saved job postings, goal-risk indicators, optional AI assistant (opt-in, explainable, no sensitive data by default) | Planned |
| v3.0 | Connected | GitHub OAuth evidence, calendar, offline support, desktop packaging, import/export tools, SONIC.EXE visual themes via a defined interface | Evaluate |

## Product backlog (prioritised)
| # | Item | Module | MoSCoW | Size | Depends on |
|---|---|---|---|---|---|
| 1 | psycopg `Database` implementation + PostgreSQL integration run | Platform | Must | M | ADR-003 |
| 2 | Deploy to HTTPS host, backups scheduled | Ops | Must | S | 1 or SQLite volume |
| 3 | Axe accessibility checks in E2E; fix findings | UX | Must | S | - |
| 4 | Real `@types/react` typecheck in CI | Quality | Must | XS | network |
| 5 | Password reset via email | Auth | Should | M | email provider |
| 6 | Study session engine: timer with pause/resume, background-tab safe, focused-duration only | M04 | Should | L | - |
| 7 | Daily planning algorithm (available hours, deadlines, priority, estimate, energy, dependencies, breaks, no double-booking, manual override) as a pure domain function | M14 | Should | M | - |
| 8 | Weekly review screen with reflection fields | M15 | Should | M | - |
| 9 | Goals with milestones and linked quests | M05 | Should | L | - |
| 10 | Project tracker with stage flow IDEA→MAINTENANCE | M10 | Should | L | - |
| 11 | Job application tracker, CSV import, funnel metrics | M09 | Should | L | - |
| 12 | Multi-objective boss quests | M02 | Could | M | - |
| 13 | Personal finance with integer minor units | M08 | Could | L | - |
| 14 | Wellness log (optional, private) | M07 | Could | M | - |
| 15 | Reward shop and inventory (cosmetic) | M12 | Could | M | coins ledger |
| 16 | Spaced repetition (documented algorithm, e.g. SM-2) | M04 | Could | M | 6 |
| 17 | GitHub OAuth evidence import | v3.0 | Won't (now) | L | - |
