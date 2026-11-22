import { useState } from "react";
import { api, query } from "../lib/api";
import { useQuery } from "../lib/query";
import type { Analytics } from "../lib/types";
import { addDays, humanize, num, pct, shortDay, signedXp } from "../lib/format";
import { PageHeader } from "../components/Shell";
import { ErrorState, Skeleton } from "../components/feedback";
import { BarList, ColumnChart, DataTable, Heatmap } from "../components/charts";

const RANGES = [7, 28, 90] as const;

const rateText = (rate: number | null) => (rate === null ? "no due quests" : pct(rate));

export function AnalyticsPage({ today }: { today: string }) {
  const [days, setDays] = useState<(typeof RANGES)[number]>(28);
  const [table, setTable] = useState(false);
  const qs = query({ from: addDays(today, -(days - 1)), to: today });
  const a = useQuery(`analytics${qs}`, () => api.get<Analytics>(`/analytics/summary${qs}`));

  return (
    <div>
      <PageHeader title="Analytics">
        Every number here is calculated from your recorded quests, habits and XP ledger, by your local day. Nothing is estimated.
      </PageHeader>
      <div className="flex flex-wrap gap-1 p-1 mb-6 rounded-[12px] bg-surface border border-line w-fit" role="group" aria-label="Date range">
        {RANGES.map((r) => (
          <button key={r} aria-pressed={days === r} onClick={() => setDays(r)}
            className={`px-3 py-1.5 rounded-[9px] text-sm ${days === r ? "bg-raised text-ink" : "text-ink-3 hover:text-ink"}`}>
            Last {r} days
          </button>
        ))}
      </div>
      {a.error ? <ErrorState error={a.error} onRetry={a.refetch} /> : !a.data ? <Skeleton lines={6} /> : <Report a={a.data} table={table} setTable={setTable} />}
    </div>
  );
}

function Report({ a, table, setTable }: { a: Analytics; table: boolean; setTable: (v: boolean) => void }) {
  const t = a.totals;
  const w = a.weekly;
  return (
    <div className="grid gap-6">
      <section className="panel-reward px-5 py-4 grid gap-2" aria-labelledby="insights">
        <h2 id="insights">What the data says</h2>
        {a.insights.length ? (
          <ul className="grid gap-2">
            {a.insights.map((i) => (
              <li key={i.kind}>
                <details>
                  <summary className="cursor-pointer text-ink">{i.text}</summary>
                  <p className="text-xs text-ink-3 mt-1">
                    Based on {Object.entries(i.basis).map(([k, v]) => `${humanize(k).toLowerCase()} ${v}`).join(", ")}.
                  </p>
                </details>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-ink-2">Not enough activity yet to say anything. Complete a few quests or habit days and insights will appear here.</p>
        )}
      </section>

      <section className="panel px-5 py-4 grid gap-3" aria-labelledby="xp-chart">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 id="xp-chart">Net XP per day</h2>
            <p className="text-sm text-ink-3">{shortDay(a.range.from)} to {shortDay(a.range.to)}: <span className="text-ink-2">{signedXp(t.net_xp)}</span> across {t.active_days} active {t.active_days === 1 ? "day" : "days"}.</p>
          </div>
          <button className="btn btn-ghost text-sm" onClick={() => setTable(!table)} aria-pressed={table}>{table ? "Show chart" : "Show table"}</button>
        </div>
        {table ? <DataTable points={a.series.net_xp} unit="XP" /> : <ColumnChart points={a.series.net_xp} label="Net XP per day" unit="XP" />}
      </section>

      <div className="grid lg:grid-cols-2 gap-6 items-start">
        <section className="panel px-5 py-4 grid gap-3" aria-labelledby="activity">
          <h2 id="activity">Activity</h2>
          <p className="text-sm text-ink-3">{t.quest_completions} quest completions and {t.habit_days} habit days.</p>
          <Heatmap points={a.series.activity} />
        </section>

        <section className="panel px-5 py-4 grid gap-3" aria-labelledby="week-compare">
          <h2 id="week-compare">This week compared with last</h2>
          <dl className="grid grid-cols-2 gap-y-3 text-sm">
            <dt className="text-ink-3">Quests completed</dt>
            <dd className="text-ink">{w.completions_this_week} <span className="text-ink-3">vs {w.completions_last_week}</span></dd>
            <dt className="text-ink-3">Due quests completed</dt>
            <dd className="text-ink">
              {rateText(w.completion_rate_this_week.rate)}{" "}
              <span className="text-ink-3">vs {rateText(w.completion_rate_last_week.rate)}</span>
            </dd>
          </dl>
          <p className="text-xs text-ink-3">
            The rate counts one-off quests due that week: {w.completion_rate_this_week.completed} of {w.completion_rate_this_week.counted} this
            week. Quests due later this week aren't counted until their day passes.
          </p>
        </section>

        <section className="panel px-5 py-4 grid gap-3" aria-labelledby="attr">
          <h2 id="attr">XP by attribute</h2>
          <BarList rows={a.xp_by_attribute.filter((r) => r.xp !== 0).map((r) => ({ label: humanize(r.attribute), value: r.xp }))} unit="XP" />
          {a.xp_by_attribute.every((r) => r.xp === 0) ? <p className="text-sm text-ink-3">No XP in this range yet.</p> : null}
          <p className="text-xs text-ink-3">Attributes reflect logged activity only. Unassigned means the quest had no linked skill.</p>
        </section>

        <section className="panel px-5 py-4 grid gap-3" aria-labelledby="skills-xp">
          <h2 id="skills-xp">Most practised skills</h2>
          {a.xp_by_skill.length ? <BarList rows={a.xp_by_skill.map((s) => ({ label: s.name, value: s.xp }))} unit="XP" /> : <p className="text-sm text-ink-3">Link quests to skills to see where your practice goes.</p>}
          {a.completions_by_category.length ? (
            <>
              <h3 className="mt-2">Completions by quest type</h3>
              <BarList rows={a.completions_by_category.map((c) => ({ label: humanize(c.category), value: c.count }))} unit="" />
            </>
          ) : null}
        </section>
      </div>

      <details className="panel px-5 py-4">
        <summary className="cursor-pointer">How these metrics are defined</summary>
        <dl className="grid gap-2 mt-3 text-sm">
          {Object.entries(a.definitions).map(([k, v]) => (
            <div key={k}><dt className="text-ink">{humanize(k)}</dt><dd className="text-ink-2">{v}</dd></div>
          ))}
          <div><dt className="text-ink">Local day</dt><dd className="text-ink-2">Days follow {a.range.timezone} and start at {num(a.range.day_start_hour)}:00, so late-night work counts toward the day you were in.</dd></div>
        </dl>
      </details>
    </div>
  );
}
