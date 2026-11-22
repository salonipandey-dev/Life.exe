import { useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { invalidate, useMutation, useQuery } from "../lib/query";
import type { Habit } from "../lib/types";
import { humanize, pct, weekdayName } from "../lib/format";
import { PageHeader } from "../components/Shell";
import { Dialog } from "../components/Dialog";
import { EmptyState, ErrorState, FormError, InlineError, Skeleton, toast } from "../components/feedback";
import { DayStrip, HabitDayMenu, HabitRow } from "../components/habits";

const ATTRIBUTES = ["DISCIPLINE", "STRENGTH", "INTELLECT", "KNOWLEDGE", "CREATIVITY", "COMMUNICATION", "FINANCIAL_LITERACY", "CAREER_DEVELOPMENT"];

export function HabitsPage() {
  const [archived, setArchived] = useState(false);
  const key = `habits${archived ? "?include_archived=true" : ""}`;
  const list = useQuery(key, () => api.get<{ items: Habit[]; today: string }>(`/habits${archived ? "?include_archived=true" : ""}`));
  const [creating, setCreating] = useState(false);

  return (
    <div>
      <PageHeader title="Habits" action={<button className="btn btn-primary" onClick={() => setCreating(true)}>New habit</button>}>
        Rest days and paused days don't break a streak, and a missed day never removes XP. Each completed day earns 5 XP.
      </PageHeader>
      <label className="flex items-center gap-2 text-sm text-ink-2 mb-4">
        <input type="checkbox" checked={archived} onChange={(e: { target: { checked: boolean } }) => setArchived(e.target.checked)} />
        Show archived habits
      </label>
      {list.error ? <ErrorState error={list.error} onRetry={list.refetch} /> : !list.data ? <Skeleton lines={4} /> : list.data.items.length === 0 ? (
        <div className="panel">
          <EmptyState title="Start with one small habit" action={<button className="btn btn-quiet" onClick={() => setCreating(true)}>New habit</button>}>
            Something you can do on a busy day: a 20-minute walk, ten pages, one algorithm problem.
          </EmptyState>
        </div>
      ) : (
        <div className="grid gap-4">
          {list.data.items.map((h) => <HabitCard key={h.id} habit={h} today={list.data!.today} />)}
        </div>
      )}
      <Dialog open={creating} title="New habit" onClose={() => setCreating(false)}>
        <HabitForm onDone={() => setCreating(false)} />
      </Dialog>
    </div>
  );
}

function HabitCard({ habit, today }: { habit: Habit; today: string }) {
  const toggle = useMutation(async (path: string) => {
    await api.post(`/habits/${habit.id}/${path}`);
    invalidate("habits", "dashboard");
  });
  return (
    <section className="panel px-5 pt-1 pb-4 grid gap-3" aria-label={habit.name}>
      <ul><HabitRow habit={habit} today={today} /></ul>
      <DayStrip days={habit.calendar} />
      <dl className="flex flex-wrap gap-x-8 gap-y-1 text-sm">
        {habit.stats.windows.map((w) => (
          <div key={w.label}>
            <dt className="text-ink-3">{w.label}</dt>
            <dd className="text-ink">
              {pct(w.rate)}
              {w.required ? <span className="text-ink-3"> ({w.achieved} of {w.required} {habit.stats.unit}s)</span> : null}
            </dd>
          </div>
        ))}
        <div>
          <dt className="text-ink-3">Longest streak</dt>
          <dd className="text-ink">{habit.stats.longest_streak} {habit.stats.unit}{habit.stats.longest_streak === 1 ? "" : "s"}</dd>
        </div>
        <div>
          <dt className="text-ink-3">Builds</dt>
          <dd className="text-ink">{humanize(habit.attribute)}</dd>
        </div>
      </dl>
      <div className="flex flex-wrap gap-2 items-center">
        {!habit.archived && habit.schedule_kind !== "WEEKLY_COUNT" ? <HabitDayMenu habit={habit} today={today} /> : null}
        {!habit.archived ? (
          <button className="btn btn-quiet" disabled={toggle.pending} onClick={() => toggle.run(habit.paused ? "resume" : "pause")}>
            {habit.paused ? "Resume" : "Pause"}
          </button>
        ) : null}
        <button className="btn btn-ghost" disabled={toggle.pending} onClick={() => toggle.run(habit.archived ? "unarchive" : "archive")}>
          {habit.archived ? "Unarchive" : "Archive"}
        </button>
        <InlineError error={toggle.error} />
      </div>
    </section>
  );
}

function HabitForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"DAILY" | "WEEKDAYS" | "WEEKLY_COUNT">("DAILY");
  const [days, setDays] = useState<number[]>([0, 2, 4]);
  const [perWeek, setPerWeek] = useState("3");
  const [measure, setMeasure] = useState<"BOOLEAN" | "COUNT" | "DURATION">("BOOLEAN");
  const [target, setTarget] = useState("1");
  const [attribute, setAttribute] = useState("DISCIPLINE");
  const save = useMutation(async () =>
    api.post<Habit>("/habits", {
      name: name.trim(),
      schedule_kind: kind,
      weekdays: kind === "WEEKDAYS" ? days : [0, 1, 2, 3, 4, 5, 6],
      target_per_week: kind === "WEEKLY_COUNT" ? Number(perWeek) : null,
      measure,
      target_value: measure === "BOOLEAN" ? 1 : Number(target),
      attribute,
    }),
  );
  const fields = save.error instanceof ApiError ? save.error.fieldErrors() : {};
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (await save.run()) {
      invalidate("habits", "dashboard");
      toast({ tone: "info", title: "Habit created" });
      onDone();
    }
  }
  return (
    <form className="grid gap-4" onSubmit={submit} noValidate>
      <label className="field">
        Name
        <input className="input" value={name} maxLength={80} autoFocus placeholder="Walk 20 minutes"
          onChange={(e: { target: { value: string } }) => setName(e.target.value)} />
        {fields.name ? <span className="text-danger text-xs">{fields.name}</span> : null}
      </label>
      <label className="field">
        How often
        <select className="input" value={kind} onChange={(e: { target: { value: string } }) => setKind(e.target.value as typeof kind)}>
          <option value="DAILY">Every day</option>
          <option value="WEEKDAYS">On specific days</option>
          <option value="WEEKLY_COUNT">A number of times per week</option>
        </select>
      </label>
      {kind === "WEEKDAYS" ? (
        <fieldset className="grid gap-2">
          <legend className="text-sm text-ink-2 mb-1">Days</legend>
          <div className="flex flex-wrap gap-1.5">
            {[0, 1, 2, 3, 4, 5, 6].map((d) => (
              <button type="button" key={d} aria-pressed={days.includes(d)}
                className={`chip px-3 py-1 ${days.includes(d) ? "chip-active" : ""}`}
                onClick={() => setDays((prev) => (prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d].sort()))}>
                {weekdayName(d)}
              </button>
            ))}
          </div>
        </fieldset>
      ) : null}
      {kind === "WEEKLY_COUNT" ? (
        <label className="field">
          Times per week
          <input className="input" type="number" min={1} max={7} value={perWeek} onChange={(e: { target: { value: string } }) => setPerWeek(e.target.value)} />
        </label>
      ) : null}
      <div className="grid grid-cols-2 gap-3">
        <label className="field">
          Track as
          <select className="input" value={measure} onChange={(e: { target: { value: string } }) => setMeasure(e.target.value as typeof measure)}>
            <option value="BOOLEAN">Done or not</option>
            <option value="COUNT">A count</option>
            <option value="DURATION">Minutes</option>
          </select>
        </label>
        {measure !== "BOOLEAN" ? (
          <label className="field">
            Daily target
            <input className="input" type="number" min={1} max={1440} value={target} onChange={(e: { target: { value: string } }) => setTarget(e.target.value)} />
          </label>
        ) : null}
      </div>
      <label className="field">
        Attribute it builds
        <select className="input" value={attribute} onChange={(e: { target: { value: string } }) => setAttribute(e.target.value)}>
          {ATTRIBUTES.map((a) => <option key={a} value={a}>{humanize(a)}</option>)}
        </select>
      </label>
      <FormError error={save.error} shown={["name"]} />
      <div className="flex justify-end">
        <button className="btn btn-primary" disabled={save.pending || !name.trim() || (kind === "WEEKDAYS" && days.length === 0)}>Create habit</button>
      </div>
    </form>
  );
}
