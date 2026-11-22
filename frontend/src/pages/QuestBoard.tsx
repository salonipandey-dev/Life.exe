import { useState } from "react";
import { api, query } from "../lib/api";
import { invalidate, useMutation, useQuery } from "../lib/query";
import type { Profile, Quest, QuestAction, QuestList } from "../lib/types";
import { ACTION_LABELS, dueLabel, humanize, shortDay, signedXp } from "../lib/format";
import { PageHeader } from "../components/Shell";
import { Dialog } from "../components/Dialog";
import { EmptyState, ErrorState, InlineError, Skeleton, toast } from "../components/feedback";
import { DifficultyPips, QuestForm, QuestRow, useQuestActions } from "../components/quests";

const VIEWS = {
  open: { label: "Open", status: "DRAFT,AVAILABLE,ACTIVE,PAUSED" },
  done: { label: "Completed", status: "COMPLETED" },
  closed: { label: "Cancelled or expired", status: "CANCELLED,EXPIRED" },
  all: { label: "All", status: "" },
} as const;

type View = keyof typeof VIEWS;

export function QuestBoard({ today }: { today: string }) {
  const [view, setView] = useState<View>("open");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("-priority");
  const [archived, setArchived] = useState(false);
  const [limit, setLimit] = useState(25);
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const profile = useQuery("profile", () => api.get<Profile>("/profile"));

  const qs = query({ status: VIEWS[view].status, q: search.trim(), category, sort, include_archived: archived || undefined, limit });
  const list = useQuery(`quests${qs}`, () => api.get<QuestList>(`/quests${qs}`));

  return (
    <div>
      <PageHeader title="Quest board" action={<button className="btn btn-primary" onClick={() => setCreating(true)}>New quest</button>}>
        Every quest's XP comes from its difficulty. Start a quest when you begin it; complete it when the "done when" is true.
      </PageHeader>

      <div className="flex flex-wrap items-center gap-2 mb-4" role="group" aria-label="Filters">
        <div className="flex flex-wrap gap-1 p-1 rounded-[12px] bg-surface border border-line">
          {(Object.keys(VIEWS) as View[]).map((v) => (
            <button key={v} aria-pressed={view === v} onClick={() => setView(v)}
              className={`px-3 py-1.5 rounded-[9px] text-sm ${view === v ? "bg-raised text-ink" : "text-ink-3 hover:text-ink"}`}>
              {VIEWS[v].label}
            </button>
          ))}
        </div>
        <input className="input max-w-[220px] min-h-9" type="search" placeholder="Search quests" aria-label="Search quests"
          value={search} onChange={(e: { target: { value: string } }) => setSearch(e.target.value)} />
        <select className="input w-auto min-h-9" aria-label="Quest type" value={category} onChange={(e: { target: { value: string } }) => setCategory(e.target.value)}>
          <option value="">All types</option>
          {["MAIN", "SIDE", "DAILY", "WEEKLY", "MILESTONE", "CHALLENGE", "BOSS"].map((c) => <option key={c} value={c}>{humanize(c)}</option>)}
        </select>
        <select className="input w-auto min-h-9" aria-label="Sort" value={sort} onChange={(e: { target: { value: string } }) => setSort(e.target.value)}>
          <option value="-priority">Priority</option>
          <option value="due_date">Due date</option>
          <option value="-created_at">Newest</option>
          <option value="title">Title</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-ink-2 ml-1">
          <input type="checkbox" checked={archived} onChange={(e: { target: { checked: boolean } }) => setArchived(e.target.checked)} />
          Show archived
        </label>
      </div>

      <section className="panel px-5 pt-2 pb-2" aria-live="polite">
        {list.error ? <ErrorState error={list.error} onRetry={list.refetch} /> : list.loading || !list.data ? <div className="py-4"><Skeleton /></div> : list.data.items.length === 0 ? (
          search || category ? (
            <EmptyState title="No quests match">Try a different search or type.</EmptyState>
          ) : (
            <EmptyState title={view === "open" ? "No open quests" : "Nothing here yet"}
              action={view === "open" ? <button className="btn btn-quiet" onClick={() => setCreating(true)}>Create a quest</button> : undefined}>
              {view === "open" ? "A quest is one concrete thing you'll do, like \"Solve two SQL join problems\"." : null}
            </EmptyState>
          )
        ) : (
          <>
            <ul>{list.data.items.map((q) => <QuestRow key={q.id} quest={q} today={today} onOpen={(x) => setOpenId(x.id)} />)}</ul>
            <div className="flex items-center justify-between py-3 text-sm text-ink-3">
              <span>Showing {list.data.items.length} of {list.data.total}</span>
              {list.data.total > list.data.items.length ? (
                <button className="btn btn-quiet" onClick={() => setLimit((l) => Math.min(l + 25, 100))} disabled={limit >= 100}>Show more</button>
              ) : null}
            </div>
          </>
        )}
      </section>

      <Dialog open={creating} title="New quest" onClose={() => setCreating(false)}>
        <QuestForm xpTable={profile.data?.game.xp_by_difficulty} onDone={() => setCreating(false)} />
      </Dialog>
      <Dialog open={openId !== null} title="Quest" onClose={() => setOpenId(null)}>
        {openId !== null ? <QuestDetail questId={openId} today={today} onClose={() => setOpenId(null)} /> : null}
      </Dialog>
    </div>
  );
}

export function QuestDetail({ questId, today, onClose }: { questId: number; today: string; onClose: () => void }) {
  const q = useQuery(`quests/${questId}`, () => api.get<Quest>(`/quests/${questId}`));
  const profile = useQuery("profile", () => api.get<Profile>("/profile"));
  const [editing, setEditing] = useState(false);
  const actions = useQuestActions();
  const remove = useMutation(async (quest: Quest) => {
    await api.del(`/quests/${quest.id}`);
    invalidate("quests", "dashboard");
    toast({ tone: "info", title: "Quest deleted" });
    onClose();
  });
  const archive = useMutation(async (quest: Quest, on: boolean) => {
    await api.post(`/quests/${quest.id}/${on ? "archive" : "unarchive"}`);
    invalidate("quests", "dashboard");
    toast({ tone: "info", title: on ? "Quest archived" : "Quest restored from archive" });
  });

  if (q.error) return <ErrorState error={q.error} onRetry={q.refetch} />;
  if (!q.data) return <Skeleton lines={4} />;
  const quest = q.data;
  if (editing) return <QuestForm quest={quest} xpTable={profile.data?.game.xp_by_difficulty} onDone={() => { setEditing(false); invalidate(`quests/${quest.id}`); }} />;

  const canEdit = !quest.archived && ["DRAFT", "AVAILABLE", "ACTIVE", "PAUSED"].includes(quest.status);
  const canArchive = !quest.archived && ["DRAFT", "COMPLETED", "CANCELLED", "EXPIRED"].includes(quest.status);
  const due = dueLabel(quest.due_date, today);
  const run = async (a: QuestAction) => {
    await actions.run(quest, a);
    invalidate(`quests/${quest.id}`);
  };

  return (
    <div className="grid gap-5">
      <div className="grid gap-2">
        <p className="text-xl font-display">{quest.title}</p>
        <div className="flex flex-wrap items-center gap-3 text-sm text-ink-3">
          <DifficultyPips difficulty={quest.difficulty} />
          <span className="xp">{quest.xp_reward} XP</span>
          <span>{quest.coin_reward} coins</span>
          <span className="chip">{humanize(quest.status)}</span>
          {quest.archived ? <span className="chip">Archived</span> : null}
          {due ? <span className={quest.overdue ? "text-danger" : ""}>{due}</span> : null}
        </div>
      </div>
      {quest.completion_criteria ? <p className="text-ink-2"><span className="text-ink">Done when:</span> {quest.completion_criteria}</p> : null}
      {quest.description ? <p className="text-ink-2 whitespace-pre-wrap">{quest.description}</p> : null}
      <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
        <dt className="text-ink-3">Type</dt><dd>{humanize(quest.category)}</dd>
        <dt className="text-ink-3">Priority</dt><dd>{humanize(quest.priority)}</dd>
        <dt className="text-ink-3">Repeats</dt><dd>{quest.recurrence === "NONE" ? "No" : quest.recurrence === "DAILY" ? "Every day" : "Every week"}</dd>
        {quest.estimated_minutes ? <><dt className="text-ink-3">Estimate</dt><dd>{quest.estimated_minutes} min</dd></> : null}
        {quest.skill ? <><dt className="text-ink-3">Trains</dt><dd><a className="text-accent-ink hover:underline" href={`#/skills/${quest.skill.id}`}>{quest.skill.name}</a></dd></> : null}
      </dl>

      {quest.allowed_actions.length ? (
        <div className="flex flex-wrap gap-2">
          {quest.allowed_actions.map((a) => (
            <button key={a} disabled={actions.pending} onClick={() => run(a)}
              className={`btn ${a === "complete" ? "btn-primary" : a === "cancel" || a === "expire" ? "btn-ghost" : "btn-quiet"}`}>
              {ACTION_LABELS[a]}
            </button>
          ))}
        </div>
      ) : null}
      <InlineError error={actions.error ?? remove.error ?? archive.error} />

      {quest.history && quest.history.length ? (
        <section className="grid gap-2">
          <h3>History</h3>
          <ul className="text-sm">
            {quest.history.map((h) => (
              <li key={h.id} className="row py-1.5 flex justify-between gap-3">
                <span className="text-ink-2">Completed {shortDay(h.local_date)}{h.reversed_at ? ", then reopened" : ""}</span>
                <span className={h.reversed_at ? "text-ink-3 line-through" : "text-gold-ink"}>{signedXp(h.xp_awarded)}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="flex flex-wrap gap-2 justify-end border-t border-line pt-4">
        {canEdit ? <button className="btn btn-quiet" onClick={() => setEditing(true)}>Edit</button> : null}
        {canArchive ? <button className="btn btn-quiet" onClick={() => archive.run(quest, true)}>Archive</button> : null}
        {quest.archived ? <button className="btn btn-quiet" onClick={() => archive.run(quest, false)}>Unarchive</button> : null}
        {quest.completion_count === 0 && !quest.history?.length ? (
          <button className="btn btn-danger" onClick={() => { if (window.confirm("Delete this quest? This can't be undone.")) remove.run(quest); }}>Delete</button>
        ) : null}
      </div>
    </div>
  );
}
