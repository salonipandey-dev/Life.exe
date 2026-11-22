# 03 Requirements traceability matrix

Maps each requirement group to the code that implements it and the tests that verify it. Detailed acceptance criteria are in `02-requirements-srs.md`; executed results are in `testing/test-execution-report.md`.

| Requirement | Domain rule | Service / repository | API | UI | Tests |
|---|---|---|---|---|---|
| FR-AUTH-01..06 | `core/security.py`, `core/timeutil.normalize_timezone` | `services/auth.py`, `repositories/users.py` | `api/routes/auth.py` | `pages/AuthPage.tsx` | integration/test_auth_and_security.py (13), unit/test_core.py (security, tz), E2E (3) |
| FR-CHAR-01..02 | `domain/leveling.py` | `services/common.progress_dict` | `/profile`, `/dashboard`, completion response | `components/Sigil.tsx` | unit/test_leveling.py (10, ~130 parametrised cases), test_level_up_crossing_threshold, E2E quest slice |
| FR-CHAR-03..04 | `domain/character.py`, `domain/rewards.Attribute` | `services/profile.py` | `/profile` | `pages/SettingsPage.tsx` | test_linking_skill_routes_xp_to_attribute, test_profile_settings, test_title_unlocks_with_level |
| FR-QST-01..02 | `domain/quests.py` (transition table, allowed actions) | `services/quests.py`, `repositories/quests.py` | `api/routes/quests.py` | `components/quests.tsx`, `pages/QuestBoard.tsx` | unit/test_quest_rules.py (10, 70+ parametrised pairs), test_lifecycle_pause_cancel_restore_expire |
| FR-QST-03..06 | `domain/quests.occurrence_key`, `domain/rewards.capped_reward` | `QuestService.complete/reopen`, `repositories/ledger.py`, schema `ux_quest_completions_live`, `ux_xp_events_single_reversal` | `POST /quests/{id}/complete`, `/reopen` | `useQuestActions` | integration/test_quest_slice.py, integration/test_concurrency.py (5), postgres/test_postgres_schema.py |
| FR-QST-07..11 | `domain/quests.EDITABLE_STATUSES`, `is_overdue`, `GameConfig.daily_xp_cap` | `QuestService.update/delete/set_archived` | `PATCH/DELETE /quests/{id}`, `/archive` | `QuestDetail` | test_edit_rules, test_delete_and_archive_rules, test_list_filter_search_sort_paginate, test_overdue_is_flagged_not_punished, test_daily_cap_limits_xp_but_keeps_completion |
| FR-SKL-01..04 | `domain/skills.py` | `services/skills.py`, `services/seed.py` | `api/routes/skills.py` | `pages/SkillsPage.tsx` | unit/test_skill_graph.py (9), test_skill_graph_cycle_rejected_with_path, test_skill_needs_both_xp_and_evidence, test_custom_skill_crud |
| FR-HAB-01..06 | `domain/habits.py` | `services/habits.py`, `repositories/habits.py` | `api/routes/habits.py` | `components/habits.tsx`, `pages/HabitsPage.tsx` | unit/test_habit_rules.py (15), integration/test_habits_skills_api.py (habit tests), E2E habit flow |
| FR-CMD-01 | - | `ProfileService.dashboard` | `/dashboard` | `pages/CommandCenter.tsx` | test_dashboard_priorities_and_today, E2E |
| FR-ANA-01..05 | `domain/analytics.py` | `services/analytics.py`, `repositories/analytics.py` | `/analytics/summary` | `pages/AnalyticsPage.tsx`, `components/charts.tsx` | test_analytics_matches_recorded_events, test_analytics_respects_user_timezone, test_analytics_range_validation, unit analytics tests |
| FR-ACH-01 | `domain/achievements.py` | `services/achievements.py` | `/achievements` | `pages/AchievementsPage.tsx` | test_achievement_conditions, test_full_vertical_slice |
| FR-SET-01..03 | - | `ProfileService.update/export/delete_account` | `/profile`, `/account/*` | `pages/SettingsPage.tsx` | test_profile_settings, test_export_contains_data_but_no_secrets, test_delete_account_removes_every_row |
| NFR-SEC-01 | composite FKs in both schemas | all repositories filter `user_id` | 404 for foreign ids | - | integration/test_user_isolation.py (4), test_composite_fk_blocks_cross_user_links |
| NFR-SEC-02..06 | `core/security.py`, `core/logging.redact` | - | `api/routing.py` (CSRF, size, content type), `api/middleware.py` (headers) | `lib/api.ts` (CSRF header) | test_auth_and_security.py, frontend/tests/lib.test.ts (CSRF header) |
| NFR-PERF-01 | - | indexes in migrations | - | - | perf/test_performance.py |
| NFR-REL-01 | - | `core/db.py`, `core/migrations.py` | - | - | test_failed_transaction_leaves_no_partial_rows, test_failed_migration_rolls_back, test_changed_migration_is_detected |
| NFR-UX-01, NFR-A11Y-01 | - | - | - | `components/Shell.tsx`, `Dialog.tsx`, `charts.tsx` | E2E (role/label locators, mobile viewport) |
| NFR-MNT-01 | - | - | - | - | `scripts/verify.sh` (mypy --strict, ruff, tsc) |

Requirements with status **Not started** (FR-CHAR-05, FR-QST-12/13, FR-SKL-05, FR-CMD-02, later modules, NFR-OPS-02) have no implementation or tests by design.
