# ADR-007: UTC instants, user-local calendar days with a configurable day start

- Status: Accepted (2026-11-22)

## Context
Streaks, daily quests, daily XP limits and analytics all depend on "which day was this?". Users work past midnight and travel; daylight-saving time shifts offsets.

## Decision
- Instants are stored in UTC (`TIMESTAMPTZ` on PostgreSQL, fixed-width ISO strings on SQLite).
- Every event also stores its `local_date`, computed once at write time from the user's IANA zone and `day_start_hour` (0-6, default 4): `(instant in zone - day_start_hour).date()`. Wall-clock arithmetic makes this DST-safe.
- Habit and streak rules operate on calendar dates only, so DST cannot add or remove a day.
- Legacy zone names that browsers report (for example `Asia/Calcutta`) are normalised to canonical names (`Asia/Kolkata`); defect D-001.

## Consequences
- Changing time zone later does not rewrite history: past events keep the day they happened on.
- Tests cover Kolkata day boundaries and New York spring-forward and fall-back transitions.
