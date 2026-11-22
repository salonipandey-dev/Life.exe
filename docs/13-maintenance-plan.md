# 13 Maintenance plan

## Versioning
Semantic versioning. `0.x` until the MVP is deployed; `1.0.0` = MVP live. MAJOR for breaking API or data changes, MINOR for features, PATCH for fixes. API is versioned in the path (`/api/v1`); breaking changes go to `/api/v2`.

## Bug triage
| Severity | Definition | Target |
|---|---|---|
| Critical | Data loss, cross-user exposure, wrong XP totals, security hole | Fix before any other work; hotfix release |
| High | Core flow broken (sign in, complete quest, log habit) | Next release |
| Medium | Feature degraded, workaround exists | Scheduled |
| Low | Cosmetic, copy | Backlog |
Every fixed defect gets a regression test and a line in the test report's defect log.

## Dependency updates
Monthly: review Starlette, Pydantic, Uvicorn, React, esbuild, Tailwind, Playwright release notes; update pins in `backend/requirements*.txt` and `frontend/package.json`; run `./scripts/verify.sh`. Add `pip-audit` and `npm audit` to CI (open item).

## Security review
Per release: review new endpoints for user scoping, validation and CSRF; run the isolation and security suites; check headers on the deployed site. Quarterly: re-read `09-security-and-privacy.md` against the code.

## Monitoring
Health check, 5xx rate, p95 latency (see deployment guide). Weekly glance at log volume and database size.

## Backup and recovery
Nightly SQLite `.backup`, 14-day retention, weekly off-host copy; restore drill once per quarter (restore to a scratch path and run `PRAGMA integrity_check`).

## Technical-debt register
| ID | Item | Impact | Plan |
|---|---|---|---|
| TD-01 | SQLite runtime; no PostgreSQL driver | Single writer; no managed DB | psycopg `Database` + run suite on PostgreSQL (ADR-003) |
| TD-02 | In-house routing layer instead of FastAPI | Framework code to maintain | Migrate when installable (ADR-002) |
| TD-03 | In-house build, query cache, router, charts instead of Vite/TanStack/React Router/Recharts | Fewer features (no HMR, no devtools) | Swap behind the same interfaces (ADR-004) |
| TD-04 | React type shim; real `@types/react` check never run | JSX prop typos could slip past tsc | `npm install && npm run typecheck` |
| TD-05 | In-process rate limiter | Wrong limits with >1 process | Shared store only if scaling out |
| TD-06 | No automated accessibility scan | Regressions possible | Add axe-core to E2E |
| TD-07 | Dashboard recomputes habit stats per request (~49 ms p95 on a year of logs) | Fine now; grows with habits × days | Cache per day or limit history window |
| TD-08 | No dependency vulnerability scanning | Unknown CVEs | `pip-audit`, `npm audit` in CI |
| TD-09 | No admin/correction endpoint | Corrections need SQL | Add audited correction command |

## Release checklist
- [ ] `./scripts/verify.sh` green (mypy, ruff, pytest incl. PostgreSQL schema, tsc, node tests, build, E2E, perf)
- [ ] Requirements status and traceability updated
- [ ] CHANGELOG and version bumped
- [ ] New migration files in **both** dialects; `tests/postgres` green
- [ ] OpenAPI regenerated (`python backend/scripts/export_openapi.py`)
- [ ] Backup taken before deploy
- [ ] Post-deploy smoke test and health check
- [ ] Known issues reviewed
