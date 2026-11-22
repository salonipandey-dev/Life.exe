# ADR-003: SQLite runtime now, PostgreSQL schema validated in tests

- Status: Accepted for v0.1 (2026-11-22). Superseded when a PostgreSQL driver can be installed.

## Context
PostgreSQL is the target database. A PostgreSQL 16 server binary was available, but no Python driver (psycopg) or ORM could be installed. The standard library includes `sqlite3`.

## Decision
- Runtime persistence uses SQLite in WAL mode, with explicit transactions (`BEGIN IMMEDIATE` for writes) and foreign keys enabled.
- The schema is maintained in two dialect files with identical semantics: `migrations/sqlite/0001_initial.sql` (runtime) and `migrations/postgres/0001_initial.sql` (target).
- `tests/postgres/` starts a throwaway PostgreSQL 16 cluster, applies the PostgreSQL migration and proves the same integrity rules hold there: one live completion per occurrence, idempotency keys, single reversal per ledger event, composite cross-user foreign keys, check constraints and cascade deletion.
- SQL in repositories sticks to the common subset (`ON CONFLICT`, partial indexes, `RETURNING`-free inserts, `CASE`, `EXISTS`).

## Consequences
- The app is usable today with zero infrastructure; backups are a file copy (`sqlite3 .backup`).
- SQLite allows one writer at a time. That is fine for a personal app; it is also what makes our read-check-write sequences race-free. On PostgreSQL the same guarantee needs `SELECT ... FOR UPDATE` on the user's profile row at the start of each write use case (documented in the database design).
- Remaining work to switch: a `Database` implementation backed by psycopg (placeholder `?` -> `%s`, `lastrowid` -> `RETURNING id`), run the integration suite against it, then data migration. Tracked in the technical-debt register.
