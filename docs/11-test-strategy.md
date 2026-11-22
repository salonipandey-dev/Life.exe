# 11 Test strategy and test cases

## 1. Approach
Test where the logic lives, and only claim what ran.

| Level | Tool | Scope | Location |
|---|---|---|---|
| Unit (domain) | pytest | Leveling, rewards and cap, quest transitions and occurrences, streaks and consistency, skill DAG, time conversion, password hashing, rate limiter, migrations, insights | `backend/tests/unit/` |
| Integration (API + DB) | pytest + Starlette TestClient, real SQLite file per test, fixed clock | Every endpoint group; transactions; isolation; security behaviour | `backend/tests/integration/` |
| Concurrency | threads + barrier, separate clients | Duplicate completion/reopen races | `backend/tests/integration/test_concurrency.py` |
| Schema (target DB) | pytest + throwaway PostgreSQL 16 cluster via psql | Constraints, unique/partial indexes, composite FKs, cascades | `backend/tests/postgres/` |
| Frontend unit | Node test runner + tsx | Formatting, router parsing, API client (CSRF, errors), form payload mapping | `frontend/tests/` |
| End-to-end | Playwright (Chromium) against the real server and built SPA | Signup, quest slice through level-up, duplicate refusal, habit check-in, analytics, settings, sign-out/in, mobile navigation, login error | `backend/tests/e2e/` |
| Performance | pytest timing, 30 samples, p50/p95 | Dashboard, quest list, 90-day analytics, completion on 2k quests / 6k events | `backend/tests/perf/` |
| Static | mypy --strict, ruff (lint + format check), tsc --strict | Whole codebase | `scripts/verify.sh` |

Determinism: a `FixedClock` is injected, so day boundaries, DST, ISO weeks and session expiry are tested without waiting or depending on the machine's time zone.

Run everything: `./scripts/verify.sh` (JUnit XML in `test-results/`). Markers: `-m postgres`, `-m e2e`, `-m perf`.

## 2. Entry and exit criteria
- **Entry:** feature behind a requirement ID; domain rules unit-tested before wiring the API.
- **Exit (per milestone):** all suites green; no open critical or high defects; new behaviour has an integration test and, for user-visible flows, an E2E path; docs updated.

## 3. Key test cases
| ID | Case | Expected | Test |
|---|---|---|---|
| TC-LVL-01 | XP thresholds for L = 1..10, 17, 26, 101 | Table values exactly | test_known_thresholds |
| TC-LVL-02 | Boundary threshold−1 / threshold / threshold+1 for L = 2..59 | Level changes exactly at threshold | test_boundaries_exact |
| TC-LVL-03 | Integer formula vs float spec for L up to 2,000; exactness at L = 10^7 | Equal / exact | test_integer_formula_* |
| TC-QST-01 | Create → start → complete | +XP, +coins, COMPLETED, ledger row with key, achievement | test_full_vertical_slice |
| TC-QST-02 | Complete twice / three more times | 409, ledger has one row | test_duplicate_completion_rejected_without_extra_xp |
| TC-QST-03 | 12 concurrent completes | one 200, eleven 409, one ledger row | test_concurrent_completion_awards_once |
| TC-QST-04 | Crash after completion insert | Full rollback, 500 without internals, retry succeeds | test_failed_transaction_leaves_no_partial_rows |
| TC-QST-05 | Reopen then re-complete | +150, −150, +150; total 150; coins 30 | test_reopen_reverses_with_ledger_entry_and_recomplete_nets_one_award |
| TC-QST-06 | Daily quest at 03:30 vs 04:30 local (day start 4) | Same day refused, next day allowed | test_daily_recurring_quest_once_per_local_day |
| TC-QST-07 | Daily cap 200 with three Epic completions | 150, 50 (capped), 0 (capped); all completions recorded | test_daily_cap_limits_xp_but_keeps_completion |
| TC-QST-08 | Client sends xp/coins/status fields | 422 | test_client_cannot_supply_xp_or_coins |
| TC-HAB-01 | Check-in, re-log, undo, redo | +5, 0, −5, +5; ledger shows all four | test_habit_checkin_awards_once_and_undo_reverses |
| TC-HAB-02 | Rest day between done days; then two missed days | Streak 2, then 0; XP unchanged | test_streak_rest_day_and_missed_day_never_cost_xp |
| TC-HAB-03 | DST spring-forward and fall-back in New York | Correct local dates | test_dst_* |
| TC-SKL-01 | Add Pandas as prerequisite of Python | 409 naming the cycle | test_skill_graph_cycle_rejected_with_path |
| TC-SKL-02 | Evidence without XP, then XP | IN_PROGRESS, then DEMONSTRATED and dependants unlock | test_skill_needs_both_xp_and_evidence |
| TC-ANA-01 | Known event set over 3 days | Exact daily series, totals, categories, attributes | test_analytics_matches_recorded_events |
| TC-SEC-01 | User B on user A's quest (get/patch/complete/reopen/archive/delete) | 404 for all; A unchanged | test_quests_are_isolated |
| TC-SEC-02 | Missing CSRF header / foreign Origin | 403 | test_csrf_protections |
| TC-SEC-03 | Logout then replay token | 401 | test_login_logout_and_generic_errors |
| TC-SEC-04 | Delete account | All 13 user-owned tables empty for that user; other user intact | test_delete_account_removes_every_row |
| TC-PG-01 | PostgreSQL: duplicate live completion; reversed then re-complete | Rejected; allowed | test_one_live_completion_per_occurrence |
| TC-E2E-01 | Browser: signup → create Epic quest → start → complete | "Level 2 reached" toast, ring label "Level 2. 50 of 183 XP" | test_quest_slice_create_start_complete_level_up |
| TC-E2E-02 | Browser: habit, analytics insight, settings, sign out/in | All visible and persisted | test_habit_analytics_settings_and_session |
| TC-E2E-03 | Mobile viewport navigation; bad login | Pages reachable; error text shown | test_mobile_navigation_and_login_errors |

The complete list is the test code itself: 149 test functions (136 Python, 13 TypeScript), 581 executed cases after parametrisation; see the execution report.

## 4. Not covered yet
Visual regression; automated accessibility (axe); React component tests (no jsdom available); load tests with concurrent users over real HTTP; browsers other than Chromium; the PostgreSQL *runtime* (only its schema).
