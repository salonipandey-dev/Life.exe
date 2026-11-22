# ADR-005: Append-only XP ledger with idempotency keys and compensating reversals

- Status: Accepted (2026-11-22)

## Context
XP must never be awarded twice for the same occurrence, never exist without the action that earned it, and stay explainable after edits, reopens and deletions.

## Decision
- `xp_events` is append-only. Total XP is always `SUM(amount)`; no total is stored or updated independently.
- Every award has a unique `(user_id, idempotency_key)`: `quest_completion:<completion id>` or `habit_log:<log id>:award:<n>`.
- `quest_completions` has a partial unique index on `(quest_id, occurrence_key) WHERE reversed_at IS NULL`, so at most one live completion can exist per occurrence even if application checks were bypassed.
- Completion, award, coins and status change happen in one transaction.
- Reopening appends a reversal row (`amount = -original`, `reverses_event_id`), with a unique index allowing one reversal per event. The reversal is dated to the original award's local day so daily analytics stay net.
- Quests with completion history cannot be hard-deleted (the ledger refers to them); they are archived.

## Consequences
- Duplicate clicks, retries and concurrent requests are safe (tested with 12 simultaneous requests).
- A complete -> reopen -> complete loop nets exactly one award.
- Corrections are auditable: the history of every XP point is visible.
- A cached total may be added later for speed, but only as a derived value with a consistency check against the ledger.
