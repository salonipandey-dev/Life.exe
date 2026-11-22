# 07 Game mechanics specification

All rules live in `backend/lifeexe/domain/` and are enforced only on the server. The UI displays results; it never calculates XP, levels or statuses.

## 1. Leveling
Cumulative XP needed to reach level L:

    XP_required(L) = round(100 × (L − 1)^1.5),  L ≥ 1,  XP_required(1) = 0

Implementation (`domain/leveling.py`) uses integers only: `100·n^1.5 = √(10 000·n³)`, so `XP_required = round(isqrt(10 000·n³))` with an exact half-up test (`v − f² > f`). It agrees with the float formula for every level tested and stays exact for very large levels. `level_for_xp` uses exponential then binary search; there is no level cap.

| Level | Total XP | XP from previous level |
|---|---|---|
| 1 | 0 | - |
| 2 | 100 | 100 |
| 3 | 283 | 183 |
| 4 | 520 | 237 |
| 5 | 800 | 280 |
| 6 | 1,118 | 318 |
| 10 | 2,700 | 437 |
| 20 | 8,282 | 645 |
| 50 | 34,300 | 1,045 |

Each level costs at least as much as the previous one (tested up to level 500).

## 2. Quest rewards
| Difficulty | XP | Coins (XP // 5) |
|---|---|---|
| Easy | 15 | 3 |
| Medium | 35 | 7 |
| Hard | 70 | 14 |
| Epic | 150 | 30 |

Priority, category and estimated duration do **not** change XP, so relabelling work as "critical" or padding estimates earns nothing. Values are configurable in `GameConfig` and shown read-only in Settings.

## 3. Anti-duplication
1. Each completion belongs to an occurrence: `once` (one-off), local date (daily), ISO week like `2026-W47` (weekly).
2. At most one live completion per (quest, occurrence): application check plus partial unique index.
3. Each award has idempotency key `quest_completion:<completion id>`; duplicates violate a unique constraint.
4. All of it happens in one transaction; concurrent duplicates serialise and the losers get 409.

## 4. Daily XP limit
Net XP per local day (all sources) is capped at **1,500** by default. When a completion would exceed it, the completion is still recorded and visible; the award is reduced to the remaining headroom (possibly 0) and flagged `capped`. XP is never negative and nothing is taken away. Reversals free headroom only for later completions; earlier capped awards are not topped up.

## 5. Changes after completion
| Event | Effect on XP |
|---|---|
| Reopen (one-off) | Status back to ACTIVE; reversal row `-amount`, dated to the original day; coins reversed |
| Reopen (recurring) | Undoes only the current occurrence |
| Re-complete after reopen | New completion row and new award; net effect one award |
| Edit difficulty | Affects future completions only; past awards keep their recorded amounts |
| Edit while COMPLETED, CANCELLED, EXPIRED | Not allowed (409): reopen or restore first |
| Cancel / expire | No XP change (nothing was awarded, or completion must be reopened first) |
| Delete | Only quests with no completion history; otherwise archive (ledger references stay valid) |
| Archive / unarchive | No XP change |
| Missed due date | Shown as overdue; still completable for full XP; never auto-expired |

## 6. XP correction procedure
1. Never edit or delete `xp_events` rows.
2. Append a `CORRECTION` row with the signed difference and a descriptive idempotency key, e.g. `correction:2026-11-22:quest-42-double-award`.
3. Record the reason in the changelog or defect log.
4. Verify: `SELECT SUM(amount) FROM xp_events WHERE user_id = ?` matches the expected total.
(There is no admin endpoint for this yet; it is a database procedure.)

## 7. Habits
- A day is **done** when its entry value ≥ target (yes/no habits: 1). Done days award **5 XP** each, once, with the habit's attribute.
- Lowering an entry below target or deleting it reverses the award; redoing it awards again (net one).
- **Streaks** count consecutive scheduled days that are done. Rest days, paused days and unscheduled days are neutral. Today never breaks a streak. A missed day resets the current streak and nothing else.
- Weekly-count habits (N times per ISO week) have streaks in weeks; the current week, the first partial week and weeks with paused days are neutral unless met.
- Consistency windows (7/30 days, or 4/12 weeks) report achieved/required; with no required days the rate is "not enough data", never 0%.
- Entries can be added or corrected for the last 30 days, never for the future or before the habit's start.

## 8. Skills
- Skill XP = net XP of ledger events linked to the skill (from quests that train it).
- Status: **Locked** if any prerequisite is not demonstrated; **Demonstrated** if XP ≥ `xp_required` *and* evidence count ≥ `evidence_required`; **In progress** if it has any XP or evidence; otherwise **Ready to start**. Statuses are computed in topological order so locks cascade.
- Practising a locked skill still earns XP; it simply cannot be demonstrated until its prerequisites are.

## 9. Attributes
Eight attributes: Intellect, Discipline, Creativity, Strength, Knowledge, Communication, Financial Literacy, Career Development. Attribute XP = net XP whose event carries that attribute (from the linked skill or the habit). Rank = `level_for_xp(attribute XP)` using the same curve. Attributes describe logged activity only and are never reduced by inactivity.

## 10. Achievements
| Key | Title | Condition | Hidden |
|---|---|---|---|
| first_quest | First Quest Completed | ≥ 1 live quest completion | no |
| ten_quests | Ten Quests | ≥ 10 live completions | no |
| epic_quest | Epic Undertaking | ≥ 1 Epic completion | no |
| boss_slayer | Boss Slayer | ≥ 1 Boss-category completion | yes |
| level_5 | Level 5 | level ≥ 5 | no |
| first_checkin | First Check-in | ≥ 1 done habit day | no |
| streak_7 | Seven-Day Streak | longest daily-unit streak ≥ 7 | no |
| proof_of_work | Proof of Work | ≥ 1 evidence item | no |
| skill_demonstrated | Skill Demonstrated | ≥ 1 demonstrated skill | no |

Evaluation runs inside the same transaction as the triggering event and inserts with `ON CONFLICT DO NOTHING`. Achievements grant no XP and are not revoked if the trigger is later reversed.

## 11. Titles and cosmetics
Titles unlock by level: Novice 1, Apprentice 3, Adept 5, Specialist 10, Expert 20, Architect 35, Legend 50. Avatars (6 glyphs) and themes (Obsidian, Ivory) are free. None affect rewards.

## 12. Coins
Coins accrue from quest rewards (XP // 5) in their own ledger. There is no shop yet. When the shop ships (v2.0), coins will only buy cosmetics and self-defined rewards: no randomised purchases, no loot boxes, no paid boosts, never exchangeable for money.

## 13. Boss quests (planned)
The brief's weekly boss "Portfolio Builder" (three dev sessions, one milestone, tests run, progress published) needs multi-objective quests, which are not implemented. Today `BOSS` is a category label; failing a boss will never remove earned XP.
