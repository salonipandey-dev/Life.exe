# Known issues and limitations (v0.1.0)

1. **Not deployed.** The Dockerfile, compose file and deployment guide have not been executed. Acceptance criterion 10 is open.
2. **SQLite at runtime.** PostgreSQL is the target and its schema is verified, but the app cannot yet run on it (no driver was installable). Single-writer database; run one process. (ADR-003, TD-01)
3. **Frontend typed against a React shim.** `tsc` passes with `tsconfig.offline.json`; the strict check against real `@types/react` has never run. (TD-04)
4. **CI workflow unverified.** `.github/workflows/ci.yml` mirrors `scripts/verify.sh` but has not run on GitHub.
5. **No email:** no password reset, email verification or notifications.
6. **Rate limiting is per process** and resets on restart. (TD-05)
7. **Accessibility** is designed in (labels, focus, reduced motion, table views) but not audited with axe or a screen reader. (TD-06)
8. **Chromium only** in E2E.
9. **Coins have no use yet**; the reward shop is planned for v2.0.
10. **Boss quests** are a category label, not multi-objective quests.
11. **Changing a habit's schedule** reinterprets its history with the new schedule (streaks are recomputed); past XP is unaffected.
12. **Modules not started:** study engine and timer, goals, projects, career, finance, wellness, weekly review, daily planner, reward shop, integrations.
