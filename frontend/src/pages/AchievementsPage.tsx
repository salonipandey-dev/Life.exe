import { api } from "../lib/api";
import { useQuery } from "../lib/query";
import type { Achievement } from "../lib/types";
import { shortDay } from "../lib/format";
import { PageHeader } from "../components/Shell";
import { ErrorState, Skeleton } from "../components/feedback";

export function AchievementsPage() {
  const q = useQuery("achievements", () => api.get<{ achievements: Achievement[]; unlocked_count: number; total: number }>("/achievements"));
  if (q.error) return <ErrorState error={q.error} onRetry={q.refetch} />;
  if (!q.data) return <Skeleton lines={4} />;
  const groups = [...new Set(q.data.achievements.map((a) => a.category))];
  return (
    <div>
      <PageHeader title="Achievements">
        {q.data.unlocked_count} of {q.data.total} unlocked. Each one is awarded from something you actually recorded.
      </PageHeader>
      <div className="grid gap-8">
        {groups.map((g) => (
          <section key={g} aria-labelledby={`ach-${g}`} className="grid gap-3">
            <h2 id={`ach-${g}`} className="text-xl">{g}</h2>
            <ul className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {q.data!.achievements.filter((a) => a.category === g).map((a) => (
                <li key={a.key} className={`px-4 py-4 grid gap-1 ${a.unlocked ? "panel-reward" : "rounded-[18px] border border-dashed border-line-strong"}`}>
                  <div className="flex items-center gap-2">
                    <span aria-hidden="true" className={a.unlocked ? "text-gold" : "text-ink-3"}>{a.unlocked ? "◆" : "◇"}</span>
                    <p className={`font-display text-lg ${a.unlocked ? "text-ink" : "text-ink-2"}`}>{a.title}</p>
                  </div>
                  <p className="text-sm text-ink-2">{a.description}</p>
                  <p className="text-xs text-ink-3">{a.unlocked && a.unlocked_at ? `Unlocked ${shortDay(a.unlocked_at.slice(0, 10))}` : "Not yet"}</p>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
