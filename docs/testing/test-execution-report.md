# Test execution report: v0.1.0

Run: `./scripts/verify.sh` on branch `feature/mvp-foundation-quest-slice`, 2026-11-22 12:37:37–12:38:00 UTC (23 s). Exit code 0. Every number below comes from that run's console output and JUnit files; nothing is estimated.

## Environment
| Item | Value |
|---|---|
| OS | Linux 6.18 x86_64 (glibc 2.39), 2 vCPU, 7 GiB RAM, cloud sandbox |
| Python | 3.13.18; Starlette 1.7.0, Pydantic 2.13.5, Uvicorn 0.54.0, pytest 9.1.1, mypy 2.3.1, ruff 0.16.9 |
| SQLite | 3.53.1 (WAL) |
| PostgreSQL | 16 (server binaries; throwaway cluster per run) |
| Node | 22.23.5; TypeScript 6.0.3, esbuild 0.28.2, Tailwind 4.3.3, tsx 4.23.12 |
| Browser | Playwright 1.63.0, Chromium (headless) build 1243 |
| Note | No package installation was possible. `frontend/node_modules` was symlinked to the pre-installed global packages, and the frontend was type-checked with `tsconfig.offline.json` (React type shim) because `@types/react` was unavailable. |

## Results
| Stage | Result |
|---|---|
| mypy --strict (51 files) | Pass, 0 issues |
| ruff lint + format check (71 files) | Pass |
| Backend unit (`tests/unit`) | 503 passed |
| Backend integration (`tests/integration`) | 55 passed |
| PostgreSQL schema (`tests/postgres`) | 6 passed |
| Frontend type check (offline config) | Pass |
| Frontend unit (`frontend/tests`) | 13 passed |
| Frontend production build | Pass: 264.8 KiB JS, 25.3 KiB CSS (minified, before gzip) |
| End-to-end, Chromium (`tests/e2e`) | 3 passed |
| Performance budgets (`tests/perf`) | 1 passed |
| **Total executed test cases** | **581 passed, 0 failed, 0 skipped** |

## Performance (in-process, single user)
Dataset: 2,031 quests, 6,000 completions and ledger rows over a year, 5 habits with ~1,300 logs. 30 samples after warm-up.

| Operation | p50 | p95 | Target p95 |
|---|---|---|---|
| GET /dashboard | 45.8 ms | 48.9 ms | < 250 ms |
| GET /quests (50 open) | 7.7 ms | 8.1 ms | < 150 ms |
| GET /analytics/summary (90 days) | 11.4 ms | 12.5 ms | < 250 ms |
| POST /quests/{id}/complete | 24.2 ms | 25.9 ms | < 150 ms |

These measure application and database time without network latency, on one user. They are not load-test results.

## Defect log
| ID | Found by | Severity | Description | Fix | Regression test |
|---|---|---|---|---|---|
| D-001 | E2E signup | High | Chromium reports the time zone `Asia/Calcutta`; the installed tz database has no legacy links, so registration failed with 422 | Normalise legacy names to canonical zones (`Asia/Kolkata`) on input | test_register_accepts_legacy_browser_timezone, test_legacy_timezone_aliases_normalize |
| D-002 | E2E signup | Medium | A 422 on a field without its own input (time zone) showed no message at all | `FormError` shows unmapped field errors | E2E signup path |
| D-003 | E2E settings | Medium | Settings time-zone select could not show the saved canonical zone when the browser lists only legacy names | Always include the saved zone in the options | test_habit_analytics_settings_and_session |
| D-004 | Integration (weekly quest) | n/a (test bug) | Test advanced the clock to 03:30 local and expected a new day, but the 04:00 day start correctly kept it on the old day | Test corrected; the behaviour was right | test_weekly_recurring_quest_once_per_iso_week |
| D-005 | Demo seeding | Low | Seeding 21 days through the API outlived the 14-day session, giving 401 mid-seed (expected behaviour) | Demo script uses a longer TTL | n/a |
| D-006 | Visual review | Low | Tailwind candidate extraction split arbitrary values containing commas/parentheses, so `grid-cols-[minmax(...)]` was missing; heatmap scaled to full width | Tokenizer keeps such values; heatmap uses natural pixel size | Screenshot review |
| D-007 | Visual review | Low | Dashboard ranked a dated LOW-priority quest above an undated CRITICAL one | Urgency = overdue → due today → priority | test_dashboard_priorities_and_today |
| D-008 | Lint | Low | 78 ruff findings on first run (ambiguous names, legacy typing, long lines, unscoped SQL warnings) | Fixed; S608 ignored only in whitelisted-SQL modules with rationale | ruff in verify.sh (blocking) |
| D-009 | Contrast check | Medium | Ivory label on Primary Emerald buttons measured 4.3:1 (below AA 4.5:1 for 14 px text) | White label: 5.0:1 | Documented contrast table in UI spec |

Open critical or high defects: **none known.**

## Regression
The full suite runs on every `verify.sh` invocation; all nine defects above have either a regression test or a blocking check.

## Not executed (and therefore not claimed)
- Type check against real `@types/react` (`npm run typecheck`): packages unavailable.
- Docker image build and `docker compose up`.
- GitHub Actions CI workflow (no runner here; the workflow mirrors `verify.sh`).
- Application runtime on PostgreSQL (only the schema is tested there).
- Browsers other than Chromium; automated accessibility scan; load testing over real HTTP.
- Deployment to a public HTTPS host.
