import { useCallback, useState } from "react";
import { api } from "../lib/api";
import { invalidate, useMutation } from "../lib/query";
import type { DayState, Habit, HabitLogResult } from "../lib/types";
import { humanize, parseDay, shortDay, streakLabel, weekdayName } from "../lib/format";
import { InlineError, toast } from "./feedback";

const STATE_STYLE: Record<DayState, string> = {
  DONE: "bg-accent border-accent",
  PARTIAL: "border-accent bg-accent-deep",
  REST: "border-line-strong bg-transparent",
  PAUSED: "border-line bg-transparent opacity-50",
  MISSED: "border-line bg-raised",
  PENDING: "border-line-strong border-dashed bg-transparent",
  OPEN: "border-line bg-transparent",
  NOT_SCHEDULED: "border-transparent bg-transparent opacity-30",
  BEFORE_START: "border-line border-dotted bg-transparent opacity-40",
};

const STATE_WORDS: Record<DayState, string> = {
  DONE: "done",
  PARTIAL: "partly done",
  REST: "rest day",
  PAUSED: "paused",
  MISSED: "not done",
  PENDING: "not yet done",
  OPEN: "no entry",
  NOT_SCHEDULED: "not scheduled",
  BEFORE_START: "before start",
};

export function DayStrip({ days, compact = false }: { days: Habit["calendar"]; compact?: boolean }) {
  return (
    <ol className={`flex ${compact ? "gap-1" : "gap-1.5"}`} aria-label="Recent days">
      {days.map((d) => (
        <li
          key={d.date}
          title={`${shortDay(d.date)}: ${STATE_WORDS[d.state]}`}
          aria-label={`${shortDay(d.date)}: ${STATE_WORDS[d.state]}`}
          className={`${compact ? "size-3" : "size-4"} rounded-[4px] border ${STATE_STYLE[d.state]}`}
        />
      ))}
    </ol>
  );
}

export function useHabitLog() {
  const fn = useCallback(async (habit: Habit, body: Record<string, unknown>, undo = false) => {
    const r = undo
      ? await api.del<HabitLogResult>(`/habits/${habit.id}/logs/${body.date}`)
      : await api.post<HabitLogResult>(`/habits/${habit.id}/logs`, body);
    if (r.xp_delta > 0) toast({ tone: "reward", title: `${habit.name}: done`, body: `+${r.xp_delta} XP` }, 3500);
    for (const a of r.achievements_unlocked) toast({ tone: "reward", title: `Achievement: ${a.title}`, body: a.description }, 7000);
    invalidate("dashboard", "habits", "profile", "analytics", "achievements");
    return r;
  }, []);
  return useMutation(fn);
}

function scheduleText(h: Habit): string {
  if (h.schedule_kind === "DAILY") return "Every day";
  if (h.schedule_kind === "WEEKLY_COUNT") return `${h.target_per_week} times a week`;
  return h.weekdays.map(weekdayName).join(", ");
}

function targetText(h: Habit): string {
  if (h.measure === "COUNT") return `Target ${h.target_value} a day`;
  if (h.measure === "DURATION") return `Target ${h.target_value} min a day`;
  return "";
}

export function HabitRow({ habit, today, showCalendar = false }: { habit: Habit; today: string; showCalendar?: boolean }) {
  const log = useHabitLog();
  const [value, setValue] = useState("");
  const state = habit.today.state;
  const done = state === "DONE";
  const isRest = habit.today.entry_type === "REST";
  const disabled = log.pending || habit.paused || habit.archived;
  const s = habit.stats;
  return (
    <li className="row py-3.5 grid gap-2">
      <div className="flex items-center gap-3">
        {habit.measure === "BOOLEAN" ? (
          <button
            role="checkbox"
            aria-checked={done}
            aria-label={`${habit.name}: mark ${done ? "not done" : "done"} today`}
            disabled={disabled}
            onClick={() => (done ? log.run(habit, { date: today }, true) : log.run(habit, {}))}
            className={`size-7 shrink-0 rounded-full border-2 grid place-items-center transition-colors ${done ? "bg-accent border-accent text-on-accent" : "border-line-strong hover:border-accent-ink"}`}
          >
            {done ? "✓" : ""}
          </button>
        ) : (
          <form
            className="flex items-center gap-1.5"
            onSubmit={(e: { preventDefault(): void }) => {
              e.preventDefault();
              if (value !== "") log.run(habit, { value: Number(value) }).then(() => setValue(""));
            }}
          >
            <input
              className="input w-16 min-h-8 py-1 text-center"
              inputMode="numeric"
              type="number"
              min={0}
              max={1440}
              aria-label={`${habit.name}: today's ${habit.measure === "DURATION" ? "minutes" : "count"}`}
              placeholder={String(habit.today.value || 0)}
              value={value}
              disabled={disabled}
              onChange={(e: { target: { value: string } }) => setValue(e.target.value)}
            />
            <button className="btn btn-quiet min-h-8 px-2.5" disabled={disabled || value === ""}>Log</button>
          </form>
        )}
        <div className="min-w-0 flex-1">
          <p className={`font-medium ${done ? "text-ink-2" : "text-ink"}`}>{habit.name}</p>
          <p className="text-xs text-ink-3">
            {[scheduleText(habit), targetText(habit), habit.paused ? "Paused" : isRest ? "Rest day today" : ""].filter(Boolean).join(". ")}
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm text-ink">{streakLabel(s.current_streak, s.unit)}</p>
          {s.week_progress ? (
            <p className="text-xs text-ink-3">{s.week_progress[0]} of {s.week_progress[1]} this week</p>
          ) : (
            <p className="text-xs text-ink-3">Best {s.longest_streak}</p>
          )}
        </div>
      </div>
      {showCalendar ? <DayStrip days={habit.calendar.slice(-14)} /> : null}
      <InlineError error={log.error} />
    </li>
  );
}

export function HabitDayMenu({ habit, today }: { habit: Habit; today: string }) {
  const log = useHabitLog();
  const restToday = habit.today.entry_type === "REST";
  return (
    <div className="flex flex-wrap gap-2">
      <button className="btn btn-quiet" disabled={log.pending || habit.paused}
        onClick={() => (restToday ? log.run(habit, { date: today }, true) : log.run(habit, { entry_type: "REST" }))}>
        {restToday ? "Undo rest day" : "Take a rest day"}
      </button>
      <InlineError error={log.error} />
    </div>
  );
}

export function weekdayHeader(days: Habit["calendar"]): string[] {
  return days.map((d) => weekdayName(parseDay(d.date).weekday).slice(0, 1));
}

export { humanize };
