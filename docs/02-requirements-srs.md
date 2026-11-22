# 02 Software Requirements Specification (SRS)

Version 0.1.0, 2026-11-22. Priorities use MoSCoW (M = Must, S = Should, C = Could, W = Won't for this release). Status values: **Done** (implemented and verified by the named tests), **Partial**, **Not started**. Test names refer to functions under `backend/tests/` (Python) and `frontend/tests/` (TypeScript); "E2E" means `backend/tests/e2e/test_browser_flows.py`.

## 1. Functional requirements

### 1.1 Identity and accounts (M01)
| ID | Requirement | Rationale | Pri | Deps | Acceptance criteria | Verified by | Status |
|---|---|---|---|---|---|---|---|
| FR-AUTH-01 | Register with email, password (10-128 chars), display name and time zone | Separate accounts from day one | M | - | 201 + session cookie; email normalised to lowercase; duplicate email 409; invalid input 422 without echoing values | test_register_sets_secure_session_cookie, test_registration_validation, test_duplicate_email_conflict | Done |
| FR-AUTH-02 | Sign in and sign out | Basic access | M | 01 | Wrong password and unknown email give the same 401; logout revokes the token server-side | test_login_logout_and_generic_errors, E2E settings/session | Done |
| FR-AUTH-03 | Sessions expire after 14 days | Limit stolen-cookie lifetime | M | 02 | Request after expiry returns 401 | test_session_expiry | Done |
| FR-AUTH-04 | Change password; other sessions are signed out | Account recovery hygiene | S | 02 | Old password required; other devices get 401 | test_change_password_revokes_other_sessions | Done |
| FR-AUTH-05 | Rate-limit auth endpoints | Brute-force protection | M | - | Over the limit returns 429 with Retry-After | test_login_rate_limited | Done |
| FR-AUTH-06 | Accept legacy browser time-zone names | Chromium reports Asia/Calcutta | M | 01 | Stored as canonical Asia/Kolkata | test_register_accepts_legacy_browser_timezone | Done |

### 1.2 Character and leveling (M01, Phase 7)
| ID | Requirement | Rationale | Pri | Deps | Acceptance criteria | Verified by | Status |
|---|---|---|---|---|---|---|---|
| FR-CHAR-01 | Level from cumulative XP: `XP_required(L) = round(100*(L-1)^1.5)`, level 1 at 0 XP | Deterministic, explainable curve | M | LEDGER | Exact integer results; boundaries L-1/L at threshold-1/threshold | test_known_thresholds, test_boundaries_exact, test_integer_formula_matches_float_definition | Done |
| FR-CHAR-02 | Show level, total XP, XP into level and XP to next level | Visible progress | M | 01 | Dashboard/profile return `progress`; UI ring reflects it | test_level_progress_fields, E2E quest slice | Done |
| FR-CHAR-03 | Eight attributes derived from XP of linked skills/habits | Reflect logged activity only | M | SKILL | Profile lists 8 attributes with XP and rank | test_linking_skill_routes_xp_to_attribute | Done |
| FR-CHAR-04 | Titles unlock by level; avatars and themes are cosmetic | Customisation without advantage | S | 01 | Locked title rejected with unlock level in message | test_profile_settings, test_title_unlocks_with_level | Done |
| FR-CHAR-05 | Unlockable cosmetics and banners | Engagement | C | SHOP | - | - | Not started |

### 1.3 Quests (M02)
| ID | Requirement | Rationale | Pri | Deps | Acceptance criteria | Verified by | Status |
|---|---|---|---|---|---|---|---|
| FR-QST-01 | Create quests with title, description, category, priority, difficulty, recurrence, estimate, due date, completion criteria, linked skill | Core planning unit | M | AUTH | 201; XP/coins derived from difficulty; client-supplied XP/status rejected (422) | test_full_vertical_slice, test_client_cannot_supply_xp_or_coins | Done |
| FR-QST-02 | Lifecycle DRAFT->AVAILABLE->ACTIVE->COMPLETED with PAUSED, CANCELLED, EXPIRED; explicit transition validation | Predictable state | M | 01 | Every (status, action) pair either defined or 409 | test_every_pair_is_either_defined_or_rejected, test_lifecycle_pause_cancel_restore_expire | Done |
| FR-QST-03 | Complete awards XP and coins exactly once per occurrence, transactionally | Integrity | M | LEDGER | Duplicate -> 409, ledger unchanged; crash mid-way leaves no rows | test_duplicate_completion_rejected_without_extra_xp, test_failed_transaction_leaves_no_partial_rows | Done |
| FR-QST-04 | Concurrent duplicate completions award once | Integrity under retries | M | 03 | 12 simultaneous requests -> one 200, eleven 409 | test_concurrent_completion_awards_once | Done |
| FR-QST-05 | Daily and weekly recurring quests: one completion per local day / ISO week | Repeatable work without farming | M | 03, TIME | Second completion same occurrence 409; next occurrence allowed | test_daily_recurring_quest_once_per_local_day, test_weekly_recurring_quest_once_per_iso_week | Done |
| FR-QST-06 | Reopen reverses XP with a ledger entry; re-completion nets one award | Correct mistakes honestly | M | 03 | Ledger shows +150, -150, +150 | test_reopen_reverses_with_ledger_entry_and_recomplete_nets_one_award | Done |
| FR-QST-07 | Edit, reschedule; no edits in terminal states; recurrence fixed after start | Consistent rewards | M | 01 | 409 for disallowed edits | test_edit_rules | Done |
| FR-QST-08 | Delete only without completion history, otherwise archive | Ledger references stay valid | M | 06 | 409 with "Archive" hint | test_delete_and_archive_rules | Done |
| FR-QST-09 | Filter by status/category/difficulty, search, sort, paginate | Find work quickly | M | 01 | LIKE wildcards literal; invalid sort 422; limit <= 100 | test_list_filter_search_sort_paginate | Done |
| FR-QST-10 | Overdue is a derived flag; late completion still earns XP | No punitive expiry | M | 01 | Overdue quest completes with full XP | test_overdue_is_flagged_not_punished | Done |
| FR-QST-11 | Daily XP limit (default 1,500 net XP per local day); completions beyond it are recorded | Discourage meaningless farming without erasing work | S | 03 | Awards 150, 50, 0 at cap 200; all completions recorded | test_daily_cap_limits_xp_but_keeps_completion | Done |
| FR-QST-12 | Linked project/goal on quests | Roadmaps | S | GOAL | - | - | Not started |
| FR-QST-13 | Multi-objective boss quests | Engagement | C | 03 | - | - | Not started (BOSS is a category only) |

### 1.4 Skills (M03)
| ID | Requirement | Rationale | Pri | Deps | Acceptance criteria | Verified by | Status |
|---|---|---|---|---|---|---|---|
| FR-SKL-01 | Per-account editable skill catalogue seeded with 32 skills in 5 trees | Not hard-coded per user | M | AUTH | Seed on registration; user can add/edit/archive | test_custom_skill_crud | Done |
| FR-SKL-02 | Prerequisites form a DAG; cycles rejected with the cycle path | Coherent roadmaps | M | 01 | 409 naming the cycle; self-loop rejected | test_skill_graph_cycle_rejected_with_path, test_would_create_cycle | Done |
| FR-SKL-03 | Roadmap order = deterministic topological order; tiers = longest prerequisite chain | Show what to learn next | M | 02 | Prerequisites precede dependants | test_topological_order_prerequisites_first_and_deterministic, test_depth_levels | Done |
| FR-SKL-04 | Demonstrated only with XP >= requirement AND evidence >= requirement; locks cascade | Engagement vs competency | M | 02, LEDGER | XP alone never demonstrates | test_skill_needs_both_xp_and_evidence, test_xp_alone_never_demonstrates, test_statuses_cascade_locks | Done |
| FR-SKL-05 | Assessments and practice requirements per node | Richer evidence | C | 04 | - | - | Not started |

### 1.5 Habits (M06)
| ID | Requirement | Rationale | Pri | Deps | Acceptance criteria | Verified by | Status |
|---|---|---|---|---|---|---|---|
| FR-HAB-01 | Daily, specific-weekday and N-per-week habits; yes/no, count or minutes | Real schedules | M | AUTH | Validation of schedule/measure combos | test_weekly_count_habit, test_weekday_schedule_skips_unscheduled_days | Done |
| FR-HAB-02 | Log, correct and undo a day (last 30 days); rest days | Honest record | M | 01 | One award per done day; undo reverses; no future days | test_habit_checkin_awards_once_and_undo_reverses, test_backfill_rules, test_count_habit_partial_then_met | Done |
| FR-HAB-03 | Streaks and consistency respecting time zones, day start, rest days, pauses, schedules | Fair streaks | M | TIME | Rest/pause neutral; today pending; DST-safe | test_rest_day_is_neutral, test_paused_days_are_neutral, test_today_pending_does_not_break_streak, test_dst_* | Done |
| FR-HAB-04 | A missed day never removes XP or lowers attributes | Non-punitive design | M | 03 | XP unchanged after missed days | test_streak_rest_day_and_missed_day_never_cost_xp | Done |
| FR-HAB-05 | Pause/resume and archive | Life happens | S | 01 | Paused days neutral in streaks | test_pause_resume | Done |
| FR-HAB-06 | Calendar view and consistency statistics with explicit "not enough data" | Transparency | M | 03 | `rate: null` when no required days | test_consistency_windows_and_unknown_when_no_data | Done |

### 1.6 Command Center (M14)
| ID | Requirement | Rationale | Pri | Deps | Acceptance criteria | Verified by | Status |
|---|---|---|---|---|---|---|---|
| FR-CMD-01 | Character overview, top three priorities, today's quests, habits today, this week, recent XP and achievements, quick add | Daily entry point | M | QST, HAB | Priorities: overdue, due today, then priority | test_dashboard_priorities_and_today, E2E quest slice | Done |
| FR-CMD-02 | Daily planning algorithm (time blocks, breaks, dependencies) | Realistic scheduling | S | 01 | - | - | Not started |

### 1.7 Analytics (M13)
| ID | Requirement | Rationale | Pri | Deps | Acceptance criteria | Verified by | Status |
|---|---|---|---|---|---|---|---|
| FR-ANA-01 | Net XP per day, quest completions, habit days, activity heatmap, XP by attribute and skill, completions by type for a date range (<= 366 days) | Genuine analytics | M | LEDGER | Values equal recorded events exactly; reopened quests net to zero; gaps are zeros | test_analytics_matches_recorded_events, test_analytics_range_validation | Done |
| FR-ANA-02 | Days follow the user's time zone and day start | Correct attribution | M | TIME | 04:30 local counts on the new day | test_analytics_respects_user_timezone | Done |
| FR-ANA-03 | Week-over-week comparison and due-quest completion rate | Reflection | S | 01 | Rate excludes quests not yet due | test_analytics_matches_recorded_events (weekly block) | Done |
| FR-ANA-04 | Insights only when supported by data, each with its basis | No fake analytics | M | 01 | No data -> no insights; minimum sample for rate insight | test_insights_require_data, test_insight_text_and_basis | Done |
| FR-ANA-05 | Metric definitions shown to the user | Explainability | M | 01 | `definitions` in API and UI | test_analytics_matches_recorded_events | Done |

### 1.8 Achievements (M11), settings and data ownership
| ID | Requirement | Rationale | Pri | Deps | Acceptance criteria | Verified by | Status |
|---|---|---|---|---|---|---|---|
| FR-ACH-01 | Idempotent achievements from recorded events; hidden achievements; gallery | Recognition | S | QST, HAB, SKL | No duplicates; awarded in the same transaction | test_full_vertical_slice, test_achievement_conditions, E2E | Done |
| FR-SET-01 | Edit display name, avatar, title, theme, time zone, day start | Personalisation | M | AUTH | Invalid tz/avatar 400; day start 0-6 | test_profile_settings | Done |
| FR-SET-02 | Export all personal data as JSON (no secrets) | Data ownership | M | AUTH | Download contains all tables, no password or token hashes | test_export_contains_data_but_no_secrets | Done |
| FR-SET-03 | Delete account and all data with password confirmation | Right to erasure | M | AUTH | Every row for the user removed; other users untouched | test_delete_account_removes_every_row | Done |

### 1.9 Later modules (from the product brief)
FR-STD (study engine, timer, spaced repetition), FR-GOL (goals and roadmaps), FR-WEL (wellness), FR-FIN (finance, integer minor units, INR default), FR-CAR (career tracker), FR-PRJ (projects and portfolio), FR-SHP (reward shop), FR-REV (weekly review): **Not started.** See `14-roadmap-and-backlog.md`.

## 2. Non-functional requirements
| ID | Requirement | Pri | Acceptance criteria | Verified by | Status |
|---|---|---|---|---|---|
| NFR-SEC-01 | Every query scoped by user; other users' resources return 404 | M | Isolation suite passes; composite FKs reject cross-user links | test_quests_are_isolated, test_cannot_link_another_users_skill, test_composite_fk_blocks_cross_user_links | Done |
| NFR-SEC-02 | scrypt password hashing; opaque hashed session tokens; HttpOnly SameSite cookies; Secure in production | M | Hash format and verify tests; cookie flags | test_password_hash_roundtrip, test_register_sets_secure_session_cookie | Done |
| NFR-SEC-03 | CSRF defence for state-changing requests | M | Missing header or foreign Origin -> 403 | test_csrf_protections | Done |
| NFR-SEC-04 | Input validation, body size limit, JSON content type, parameterised SQL | M | 413/400/422 cases; injection payloads inert | test_content_type_size_and_json_validation, test_sql_injection_payloads_are_inert | Done |
| NFR-SEC-05 | Security headers (CSP self-only, nosniff, frame deny, referrer, HSTS in production) | M | Headers present | test_security_headers_and_error_shape | Done |
| NFR-SEC-06 | No stack traces or secrets in responses; logs redact sensitive keys | M | 500 body generic | test_failed_transaction_leaves_no_partial_rows | Done |
| NFR-PERF-01 | p95 in-process latency: dashboard < 250 ms, quest list < 150 ms, 90-day analytics < 250 ms, completion < 150 ms on 2k quests / 6k events | S | Measured | test_latency_budgets | Done (see report) |
| NFR-REL-01 | Writes are atomic; migrations are transactional and checksum-protected | M | Rollback tests | test_failed_migration_rolls_back, test_changed_migration_is_detected | Done |
| NFR-A11Y-01 | Keyboard reachable, visible focus, labelled controls, reduced motion, colour not the only signal, table view for charts | M | Implemented; Playwright uses role/label locators | E2E (role-based locators) | Partial: no automated axe audit or screen-reader test yet |
| NFR-UX-01 | Responsive from 360 px; bottom navigation on mobile | M | Mobile E2E navigates | test_mobile_navigation_and_login_errors | Done |
| NFR-OPS-01 | Health endpoint, structured JSON logs with request IDs | M | `/api/v1/health` ok | test_health_and_openapi_are_public | Done |
| NFR-OPS-02 | Production deployment over HTTPS | M | Public URL verified | - | Not started |
| NFR-PRIV-01 | No data sent to third parties or AI providers | M | No outbound calls in codebase | Code review | Done |
| NFR-MNT-01 | Typed code: mypy --strict, ruff, tsc strict | M | All pass | scripts/verify.sh | Done (tsc with offline React shim) |

## 3. Business rules
- BR-01 XP and coins are calculated only by the server from difficulty: Easy 15, Medium 35, Hard 70, Epic 150 XP; coins = XP // 5.
- BR-02 A quest occurrence is `once` (one-off), the local date (daily) or the ISO week (weekly).
- BR-03 Habit day done = entry value >= target; awards 5 XP once per done day.
- BR-04 Daily XP limit applies to net XP per local day across all sources.
- BR-05 Overdue never auto-expires a quest; EXPIRED is an explicit user action.
- BR-06 Achievements are not revoked when their triggering event is reversed and never grant XP.
- BR-07 Changing time zone does not rewrite the local date of past events.

## 4. Data requirements
Personal data: email, display name, time zone, quests, habits, skills, evidence links, XP ledger. No financial or health data is collected in v0.1. All timestamps UTC; local dates stored with each event. Retention: until the user deletes their account.

## 5. User stories (selected)
- As a student, I want to complete "Solve two SQL join problems" and see XP and my level update, so that effort feels rewarded. *(FR-QST-03, FR-CHAR-02)*
- As a user who double-taps on a slow connection, I want the second tap ignored, so that my XP stays honest. *(FR-QST-04)*
- As a night owl, I want 1 a.m. work to count for yesterday, so that my streak matches my real day. *(FR-HAB-03)*
- As someone recovering from illness, I want rest days and pauses that don't break my streak. *(FR-HAB-03, FR-HAB-05)*
- As a job seeker, I want to see which skills I've demonstrated with evidence, so that my resume claims are honest. *(FR-SKL-04)*
- As a privacy-conscious user, I want to export or delete everything. *(FR-SET-02, FR-SET-03)*

## 6. Use cases
**UC-01 Complete a quest.** Actor: signed-in user. Pre: quest ACTIVE. Main flow: user presses Complete -> server validates transition, derives occurrence, inserts completion, computes capped reward, appends XP and coin rows, updates status, evaluates achievements, commits -> UI shows reward toast, level change and updated ring. Alternates: already completed (409, no change); not started (409 invalid transition); daily cap reached (completion recorded with reduced XP); server error (rollback, generic 500).

**UC-02 Log a habit day.** Pre: habit not archived. Flow: tick or enter a value -> server upserts the day, awards or reverses XP to match "done", recomputes streaks. Alternates: future day or older than 30 days (400); paused (button disabled).

**UC-03 Add a prerequisite.** Flow: choose skill -> server checks reachability; if it would create a cycle, 409 with the cycle path; otherwise insert and recompute statuses.

## 7. Edge cases covered
Time-zone day boundaries and DST; ISO week 53 across the year boundary; concurrent duplicate requests; reopen/complete loops; overdue completion; daily cap at partial and zero headroom; skill self-loops and deep chains (5,000 nodes); LIKE wildcards in search; SQL injection payloads; oversized bodies; expired and forged sessions; account deletion with cross-table references.
