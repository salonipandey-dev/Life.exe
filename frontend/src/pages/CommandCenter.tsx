import { useState } from "react";
import { api } from "../lib/api";
import { useQuery } from "../lib/query";
import type { Dashboard, Profile, Quest } from "../lib/types";
import { num, signedXp, shortDay } from "../lib/format";
import { Sigil, XpLine } from "../components/Sigil";
import { EmptyState, ErrorState, Skeleton } from "../components/feedback";
import { QuestForm, QuestRow } from "../components/quests";
import { HabitRow } from "../components/habits";
import { Dialog } from "../components/Dialog";
import { QuestDetail } from "./QuestBoard";

export function CommandCenter() {
  const dash = useQuery("dashboard", () => api.get<Dashboard>("/dashboard"));
  const profile = useQuery("profile", () => api.get<Profile>("/profile"));
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<Quest | null>(null);

  if (dash.error) return <ErrorState error={dash.error} onRetry={dash.refetch} />;
  if (dash.loading || !dash.data) return <Skeleton lines={6} />;
  const d = dash.data;
  const c = d.character;
  const priorityIds = new Set(d.priorities.map((q) => q.id));
  const rest = d.today_quests.filter((q) => !priorityIds.has(q.id));

  return (
    <div className="grid gap-8">
      <section className="flex flex-col sm:flex-row sm:items-center gap-6 md:gap-10" aria-label="Character">
        <Sigil progress={c.progress} />
        <div className="grid gap-2 min-w-0">
          <h1 className="text-[2.75rem] md:text-[3.25rem] leading-none">{c.display_name}</h1>
          <p className="text-ink-2">{c.title}</p>
          <XpLine progress={c.progress} />
          <p className="text-sm text-ink-3">
            {num(c.coins)} coins. Today you've earned <span className="text-ink-2">{num(d.week.xp_today)}</span> of the{" "}
            {num(d.week.daily_xp_cap)} XP daily limit.
          </p>
        </div>
        <div className="sm:ml-auto">
          <button className="btn btn-primary" onClick={() => setCreating(true)}>New quest</button>
        </div>
      </section>

      <div className="grid lg:grid-cols-[1.35fr_1fr] gap-6 items-start">
        <div className="grid gap-6">
          <section className="panel px-5 pt-4 pb-2" aria-labelledby="top3">
            <h2 id="top3" className="mb-1">Today's top three</h2>
            <p className="text-sm text-ink-3 mb-2">Overdue first, then due today, then by priority.</p>
            {d.priorities.length ? (
              <ol>{d.priorities.map((q, i) => <QuestRow key={q.id} quest={q} today={d.today} rank={i + 1} onOpen={setOpen} />)}</ol>
            ) : (
              <EmptyState title="Nothing queued" action={<button className="btn btn-quiet" onClick={() => setCreating(true)}>Create a quest</button>}>
                Add a quest with a due date or priority and it will show up here.
              </EmptyState>
            )}
          </section>

          <section className="panel px-5 pt-4 pb-2" aria-labelledby="todayq">
            <h2 id="todayq" className="mb-2">Also on today</h2>
            {rest.length ? (
              <ul>{rest.map((q) => <QuestRow key={q.id} quest={q} today={d.today} onOpen={setOpen} />)}</ul>
            ) : (
              <p className="text-sm text-ink-3 pb-4">Recurring quests, active quests and anything due today appear here.</p>
            )}
          </section>
        </div>

        <div className="grid gap-6">
          <section className="panel px-5 pt-4 pb-2" aria-labelledby="habits-today">
            <div className="flex items-baseline justify-between">
              <h2 id="habits-today">Habits today</h2>
              <a href="#/habits" className="text-sm text-accent-ink hover:underline">All habits</a>
            </div>
            {d.habits.length ? (
              <ul>{d.habits.map((h) => <HabitRow key={h.id} habit={h} today={d.today} />)}</ul>
            ) : (
              <EmptyState title="No habits yet" action={<a className="btn btn-quiet" href="#/habits">Add a habit</a>}>
                Small, repeatable things: a walk, reading, two DSA problems.
              </EmptyState>
            )}
          </section>

          <section className="panel-reward px-5 py-4 grid gap-3" aria-labelledby="week">
            <h2 id="week">This week</h2>
            <p className="text-ink-2">
              <span className="xp">{signedXp(d.week.net_xp)}</span> from {d.week.quest_completions}{" "}
              {d.week.quest_completions === 1 ? "quest" : "quests"} and {d.week.habit_days} habit{" "}
              {d.week.habit_days === 1 ? "day" : "days"} since {shortDay(d.week.start)}.
            </p>
            {d.recent_xp.length ? (
              <ul className="grid gap-1.5 text-sm" aria-label="Recent XP">
                {d.recent_xp.map((e) => (
                  <li key={e.id} className="flex justify-between gap-3">
                    <span className="text-ink-2 truncate">{e.label}</span>
                    <span className={e.amount < 0 ? "text-ink-3" : "text-gold-ink"}>{signedXp(e.amount)}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            {d.recent_achievements.length ? (
              <p className="text-sm text-ink-2">
                Latest achievement: <a href="#/achievements" className="text-gold-ink hover:underline">{d.recent_achievements[0].title}</a>
              </p>
            ) : null}
          </section>
        </div>
      </div>

      <Dialog open={creating} title="New quest" onClose={() => setCreating(false)}>
        <QuestForm xpTable={profile.data?.game.xp_by_difficulty} onDone={() => setCreating(false)} />
      </Dialog>
      <Dialog open={open !== null} title={open?.title ?? "Quest"} onClose={() => setOpen(null)}>
        {open ? <QuestDetail questId={open.id} today={d.today} onClose={() => setOpen(null)} /> : null}
      </Dialog>
    </div>
  );
}
