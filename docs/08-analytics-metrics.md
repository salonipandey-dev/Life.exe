# 08 Analytics metric definitions

Pipeline: **raw events → validation (at write) → aggregation (on request) → metrics → visualisation.** Raw tables are `quest_completions`, `habit_logs` and `xp_events`; nothing derived is stored. All days are the user's *local* days (time zone + day-start hour) recorded with each event. The API returns these definitions in `definitions` and the UI shows them under "How these metrics are defined".

| Metric | Definition | Source | Notes |
|---|---|---|---|
| Net XP (per day / range) | `SUM(xp_events.amount)` grouped by `local_date` | xp_events | Includes reversals; reversals are dated to the original award's day, so a reopened quest nets to 0 on that day |
| Quest completions | Count of `quest_completions` with `reversed_at IS NULL` by `local_date` | quest_completions | A recurring quest counts once per occurrence |
| Habit days | Count of `habit_logs` with `entry_type = ENTRY` and `value >= habits.target_value` | habit_logs, habits | Rest days excluded |
| Activity | Quest completions + habit days, per day | both | Drives the heatmap |
| Active days | Days in range with activity > 0 | derived | |
| XP by attribute | Net XP in range grouped by `xp_events.attribute`; `UNASSIGNED` when the quest had no linked skill | xp_events | Fixed attribute order in charts |
| XP by skill | Net XP in range grouped by `skill_id`, top 8 with XP > 0 | xp_events | |
| Completions by quest type | Live completions in range grouped by quest category | quest_completions, quests | |
| Completions this/last week | Live completions from Monday of the current ISO week to today, vs the full previous week | quest_completions | Independent of the selected range |
| Due-quest completion rate (week) | completed ÷ counted, where counted = one-off quests due that week, not DRAFT/CANCELLED, and either COMPLETED or due before today | quests | Quests without due dates excluded; quests due later this week aren't counted until their day passes; `null` when counted = 0 ("no due quests") |
| Habit consistency window | achieved ÷ required over the last 7/30 days (or 4/12 weeks) | habit_logs | Required excludes unscheduled, rest and paused days and today-if-not-done; `null` = not enough data |
| Current / longest streak | See game mechanics §7 | habit_logs, habit_pauses | |

## Data integrity rules
- **No double counting:** reversed completions are excluded; reversal ledger rows cancel their award exactly; one live completion per occurrence is enforced by the schema.
- **Missing data is explicit:** daily series are dense (days without events are 0); unknown rates are `null` and rendered as "Not enough data" or "no due quests", never as 0%.
- **Date filtering:** `from`/`to` are inclusive local dates; maximum 366 days; default last 28 days; invalid ranges return 400.
- **Time zones:** an event's day is fixed at write time; changing time zone later doesn't move history.

## Insights
Produced by `domain/analytics.py` only when their inputs exist; each carries a `basis` with the exact numbers used (shown when expanded in the UI).

| Insight | Condition | Example |
|---|---|---|
| Quest completions | Any completions this week or last | "You completed 6 quests this week, compared with 4 last week." |
| Top attribute | Positive XP in range | "Most of your XP in this range went to Intellect (74% of 1,200 XP)." |
| Completion rate change | ≥ 3 counted quests in **both** weeks | "Your weekly quest completion rate increased from 60% to 75%." |

Wording is neutral ("changed from 75% to 60%") rather than judgmental. Percentages use integer half-up rounding. Future AI-generated insights must carry the same kind of `basis` and be opt-in.
