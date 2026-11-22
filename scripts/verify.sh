#!/usr/bin/env bash
# Runs every check the project has, in dependency order. Exits non-zero on the
# first failure. JUnit XML goes to test-results/ for the execution report.
#   ./scripts/verify.sh            # everything
#   SKIP_E2E=1 ./scripts/verify.sh # without the browser suite
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/test-results"
mkdir -p "$OUT"
TSC="${TSC:-$ROOT/frontend/node_modules/.bin/tsc}"
TSCONFIG="${TSCONFIG:-tsconfig.json}"   # use tsconfig.offline.json without @types/react

step() { printf '\n== %s\n' "$*"; }

step "backend: mypy --strict"
(cd "$ROOT/backend" && mypy)

step "backend: ruff lint + format check"
(cd "$ROOT/backend" && ruff check lifeexe tests scripts && ruff format --check lifeexe tests scripts)

step "backend: unit + integration + PostgreSQL schema tests"
(cd "$ROOT/backend" && python -m pytest -q -m "not e2e and not perf" --junitxml="$OUT/backend.junit.xml")

step "frontend: typecheck ($TSCONFIG)"
(cd "$ROOT/frontend" && "$TSC" -p "$TSCONFIG" --noEmit)

step "frontend: unit tests"
(cd "$ROOT/frontend" && node --import tsx --test --test-reporter=spec --test-reporter-destination=stdout \
   --test-reporter=junit --test-reporter-destination="$OUT/frontend.junit.xml" tests/*.test.ts)

step "frontend: production build"
(cd "$ROOT/frontend" && node scripts/build.mjs)

if [[ "${SKIP_E2E:-0}" != "1" ]]; then
  step "e2e: Playwright (Chromium)"
  (cd "$ROOT/backend" && python -m pytest -q -m e2e --junitxml="$OUT/e2e.junit.xml")
fi

step "performance budgets"
(cd "$ROOT/backend" && python -m pytest -q -m perf --junitxml="$OUT/perf.junit.xml")

printf '\nAll checks passed.\n'
