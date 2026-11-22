# Changelog

All notable changes are documented here. The project follows [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-22 (unreleased checkpoint, not deployed)

### Added
- Accounts: registration, sign in/out, 14-day revocable sessions (hashed opaque tokens, HttpOnly cookies), password change that signs out other devices, rate limiting, CSRF protection, security headers.
- Character: integer-exact leveling `round(100*(L-1)^1.5)`, eight activity-based attributes, level-gated titles, avatars, Obsidian and Ivory themes.
- Quests: full lifecycle with an explicit transition table; daily and weekly recurrence by local day / ISO week; filter, search, sort, pagination; archive; completion history.
- XP and coin ledgers: append-only, idempotency keys, one live completion per occurrence (partial unique index), compensating reversals on reopen, daily XP limit that never erases completions.
- Habits: daily, specific-weekday and N-per-week schedules; yes/no, count and minutes; rest days, pauses, 30-day corrections; DST-safe streaks and consistency with "not enough data".
- Skills: 32-skill editable catalogue per account; prerequisite DAG with cycle rejection and topological roadmap; demonstrated = XP and evidence.
- Command Center, Analytics (net XP, activity heatmap, attributes, skills, week comparison, evidence-backed insights, definitions), Achievements gallery (9, one hidden), Settings, JSON export and account deletion.
- PostgreSQL 16 schema validated by tests; SQLite runtime.
- Test suites: unit, integration, concurrency, isolation, security, PostgreSQL schema, frontend unit, Playwright E2E, performance budgets; `scripts/verify.sh`; CI workflow; Dockerfile.
- Documentation set in `docs/` with ADRs, ER diagram, OpenAPI, traceability and test report.

### Fixed
- D-001 Legacy browser time-zone names (`Asia/Calcutta`) were rejected at registration.
- D-002 Form errors for fields without their own input were silent.
- D-003 Saved time zone missing from the Settings list in Chromium.
