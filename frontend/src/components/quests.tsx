import { useCallback, useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { invalidate, useMutation, useQuery } from "../lib/query";
import type { Category, CompletionResult, Difficulty, Priority, Quest, QuestAction, Recurrence, ReopenResult, Skill } from "../lib/types";
import { ACTION_LABELS, DIFFICULTY_PIPS, dueLabel, humanize, num } from "../lib/format";
import { draftFrom, toPayload, type QuestDraft } from "../lib/questForm";
import { FormError, InlineError, toast } from "./feedback";

const AFFECTED = ["dashboard", "quests", "profile", "analytics", "skills", "achievements"];

/** Runs a quest action against the server and reports the server's verdict. */
export function useQuestActions() {
  const fn = useCallback(async (quest: Quest, action: QuestAction) => {
    if (action === "complete") {
      const r = await api.post<CompletionResult>(`/quests/${quest.id}/complete`);
      const coins = r.reward.coins_awarded ? ` and ${r.reward.coins_awarded} coins` : "";
      toast({
        tone: "reward",
        title: r.leveled_up ? `Level ${r.progress.level} reached` : "Quest complete",
        body: r.reward.capped
          ? `+${r.reward.xp_awarded} XP${coins}. You've reached today's ${num(r.reward.daily_cap)} XP limit, so this completion is recorded with reduced XP.`
          : `+${r.reward.xp_awarded} XP${coins} for "${quest.title}".`,
      });
      for (const a of r.achievements_unlocked) toast({ tone: "reward", title: `Achievement: ${a.title}`, body: a.description }, 7000);
    } else if (action === "reopen") {
      const r = await api.post<ReopenResult>(`/quests/${quest.id}/reopen`);
      toast({ tone: "info", title: "Quest reopened", body: r.xp_reversed ? `${r.xp_reversed} XP was returned to the ledger.` : undefined });
    } else {
      await api.post<Quest>(`/quests/${quest.id}/actions/${action}`);
    }
    invalidate(...AFFECTED);
  }, []);
  const m = useMutation(fn);
  const run = useCallback(
    async (quest: Quest, action: QuestAction) => {
      await m.run(quest, action);
    },
    [m],
  );
  return { run, pending: m.pending, error: m.error };
}

export function DifficultyPips({ difficulty }: { difficulty: Difficulty }) {
  const n = DIFFICULTY_PIPS[difficulty];
  return (
    <span className="inline-flex gap-0.5" aria-label={`${humanize(difficulty)} difficulty`} title={`${humanize(difficulty)} difficulty`}>
      {[1, 2, 3, 4].map((i) => (
        <span key={i} aria-hidden="true" className={i <= n ? "text-gold" : "text-ink-3 opacity-40"}>
          ◆
        </span>
      ))}
    </span>
  );
}

const PRIMARY_ORDER: QuestAction[] = ["complete", "start", "resume", "publish", "restore", "reopen"];

export function QuestRow({ quest, today, onOpen, rank }: { quest: Quest; today: string; onOpen?: (q: Quest) => void; rank?: number }) {
  const { run, pending, error } = useQuestActions();
  const primary = PRIMARY_ORDER.find((a) => quest.allowed_actions.includes(a));
  const done = quest.status === "COMPLETED" || (quest.recurrence !== "NONE" && quest.occurrence_completed);
  const due = quest.recurrence === "NONE" ? dueLabel(quest.due_date, today) : quest.recurrence === "DAILY" ? "Every day" : "Every week";
  return (
    <li className="row py-3.5 grid gap-1.5">
      <div className="flex items-center gap-3">
        {rank ? <span className="font-display text-xl text-ink-3 w-5 text-center" aria-label={`Priority ${rank}`}>{rank}</span> : null}
        <div className="min-w-0 flex-1">
          <button
            className={`text-left font-medium hover:underline underline-offset-4 decoration-line-strong ${done ? "text-ink-3 line-through decoration-ink-3" : "text-ink"}`}
            onClick={() => onOpen?.(quest)}
          >
            {quest.title}
          </button>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-3 mt-0.5">
            <DifficultyPips difficulty={quest.difficulty} />
            <span>{humanize(quest.category)} quest</span>
            {due ? <span className={quest.overdue ? "text-danger" : ""}>{due}</span> : null}
            {quest.skill ? <span>{quest.skill.name}</span> : null}
            {quest.status !== "ACTIVE" && quest.status !== "AVAILABLE" ? <span className="chip">{humanize(quest.status)}</span> : null}
            {quest.priority === "HIGH" || quest.priority === "CRITICAL" ? <span className="chip">{humanize(quest.priority)} priority</span> : null}
          </div>
        </div>
        <span className={`text-sm tabular-nums ${done ? "text-ink-3" : "xp"}`} aria-label={`${quest.xp_reward} XP reward`}>
          {done ? "Done" : `+${quest.xp_reward} XP`}
        </span>
        {primary ? (
          <button
            className={`btn ${primary === "complete" ? "btn-primary" : "btn-quiet"}`}
            disabled={pending}
            onClick={() => run(quest, primary)}
            aria-label={`${ACTION_LABELS[primary]}: ${quest.title}`}
          >
            {ACTION_LABELS[primary]}
          </button>
        ) : null}
      </div>
      <InlineError error={error} />
    </li>
  );
}

// --- create / edit form -----------------------------------------------------

function Select<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: T[]; onChange: (v: T) => void }) {
  return (
    <label className="field">
      {label}
      <select className="input" value={value} onChange={(e: { target: { value: string } }) => onChange(e.target.value as T)}>
        {options.map((o) => (
          <option key={o} value={o}>
            {humanize(o)}
          </option>
        ))}
      </select>
    </label>
  );
}

export function QuestForm({ quest, xpTable, onDone }: { quest?: Quest; xpTable?: Record<Difficulty, number>; onDone: (q: Quest) => void }) {
  const [d, setD] = useState<QuestDraft>(() => draftFrom(quest));
  const skills = useQuery("skills", () => api.get<{ skills: Skill[] }>("/skills"));
  const set = <K extends keyof QuestDraft>(k: K, v: QuestDraft[K]) => setD((prev) => ({ ...prev, [k]: v }));
  const save = useCallback(
    (draft: QuestDraft) =>
      quest
        ? api.patch<Quest>(`/quests/${quest.id}`, toPayload(draft))
        : api.post<Quest>("/quests", toPayload(draft)),
    [quest],
  );
  const m = useMutation(save);
  const fieldErrors = m.error instanceof ApiError ? m.error.fieldErrors() : {};
  const editingLocked = quest && !["DRAFT", "AVAILABLE"].includes(quest.status);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const saved = await m.run(d);
    if (saved) {
      invalidate("quests", "dashboard");
      toast({ tone: "info", title: quest ? "Quest saved" : "Quest created" });
      onDone(saved);
    }
  }

  return (
    <form className="grid gap-4" onSubmit={submit} noValidate>
      <label className="field">
        Title
        <input
          className="input"
          value={d.title}
          maxLength={120}
          required
          autoFocus
          aria-invalid={Boolean(fieldErrors.title)}
          onChange={(e: { target: { value: string } }) => set("title", e.target.value)}
          placeholder="Solve two SQL join problems"
        />
        {fieldErrors.title ? <span className="text-danger text-xs">{fieldErrors.title}</span> : null}
      </label>
      <div className="grid grid-cols-2 gap-3">
        <Select label="Difficulty" value={d.difficulty} options={["EASY", "MEDIUM", "HARD", "EPIC"] as Difficulty[]} onChange={(v) => set("difficulty", v)} />
        <Select label="Priority" value={d.priority} options={["LOW", "MEDIUM", "HIGH", "CRITICAL"] as Priority[]} onChange={(v) => set("priority", v)} />
        <Select label="Type" value={d.category} options={["MAIN", "SIDE", "DAILY", "WEEKLY", "MILESTONE", "CHALLENGE", "BOSS"] as Category[]} onChange={(v) => set("category", v)} />
        <label className="field">
          Repeats
          <select
            className="input"
            value={d.recurrence}
            disabled={Boolean(editingLocked)}
            onChange={(e: { target: { value: string } }) => set("recurrence", e.target.value as Recurrence)}
          >
            <option value="NONE">Does not repeat</option>
            <option value="DAILY">Every day</option>
            <option value="WEEKLY">Every week</option>
          </select>
        </label>
        {d.recurrence === "NONE" ? (
          <label className="field">
            Due date
            <input className="input" type="date" value={d.due_date} onChange={(e: { target: { value: string } }) => set("due_date", e.target.value)} />
          </label>
        ) : null}
        <label className="field">
          Estimate (minutes)
          <input className="input" type="number" min={1} max={1440} inputMode="numeric" value={d.estimated_minutes}
            onChange={(e: { target: { value: string } }) => set("estimated_minutes", e.target.value)} />
        </label>
      </div>
      <label className="field">
        Skill it trains
        <select className="input" value={d.skill_id} onChange={(e: { target: { value: string } }) => set("skill_id", e.target.value)}>
          <option value="">None</option>
          {(skills.data?.skills ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.tree}: {s.name}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        Done when
        <input className="input" value={d.completion_criteria} maxLength={500} placeholder="Both queries return the expected rows"
          onChange={(e: { target: { value: string } }) => set("completion_criteria", e.target.value)} />
      </label>
      <label className="field">
        Notes
        <textarea className="input" value={d.description} maxLength={2000} onChange={(e: { target: { value: string } }) => set("description", e.target.value)} />
      </label>
      {xpTable ? (
        <p className="text-sm text-ink-2">
          This quest is worth <span className="xp">{xpTable[d.difficulty]} XP</span>. XP comes from difficulty, so it can't be set by hand.
        </p>
      ) : null}
      <FormError error={m.error} shown={["title"]} />
      <div className="flex justify-end gap-2">
        <button type="submit" className="btn btn-primary" disabled={m.pending || !d.title.trim()}>
          {quest ? "Save quest" : "Create quest"}
        </button>
      </div>
    </form>
  );
}
