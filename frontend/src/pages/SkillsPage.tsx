import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { invalidate, useMutation, useQuery } from "../lib/query";
import type { Skill, SkillDetail } from "../lib/types";
import { humanize, num, shortDay } from "../lib/format";
import { navigate } from "../lib/router";
import { PageHeader } from "../components/Shell";
import { Dialog } from "../components/Dialog";
import { EmptyState, ErrorState, InlineError, Skeleton, toast } from "../components/feedback";

const STATUS_TEXT: Record<Skill["status"], string> = {
  LOCKED: "Locked",
  AVAILABLE: "Ready to start",
  IN_PROGRESS: "In progress",
  DEMONSTRATED: "Demonstrated",
};

function Meter({ value, max, label, tone }: { value: number; max: number; label: string; tone: "gold" | "accent" }) {
  const ratio = max <= 0 ? 1 : Math.min(value / max, 1);
  return (
    <div className="grid gap-1">
      <div className="flex justify-between text-xs text-ink-3"><span>{label}</span><span className="text-ink-2">{num(value)} / {num(max)}</span></div>
      <div className="h-1.5 rounded-full bg-raised" role="meter" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}>
        <div className={`h-full rounded-full ${tone === "gold" ? "bg-gold" : "bg-accent"}`} style={{ width: `${ratio * 100}%` }} />
      </div>
    </div>
  );
}

export function SkillsPage({ skillId }: { skillId?: number }) {
  const list = useQuery("skills", () => api.get<{ skills: Skill[]; trees: string[] }>("/skills"));
  const [tree, setTree] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const byId = useMemo(() => new Map((list.data?.skills ?? []).map((s) => [s.id, s])), [list.data]);

  if (list.error) return <ErrorState error={list.error} onRetry={list.refetch} />;
  if (!list.data) return <Skeleton lines={6} />;
  const trees = list.data.trees;
  const active = tree ?? trees[0];
  const inTree = list.data.skills.filter((s) => s.tree === active);
  const tiers = [...new Set(inTree.map((s) => s.tier))].sort((a, b) => a - b);

  return (
    <div>
      <PageHeader title="Skill tree" action={<button className="btn btn-quiet" onClick={() => setCreating(true)}>Add a skill</button>}>
        XP shows practice; evidence shows what you can do. A skill is demonstrated only when it has enough of both, and it
        unlocks the skills that build on it.
      </PageHeader>
      <div className="flex flex-wrap gap-1 p-1 mb-5 rounded-[12px] bg-surface border border-line w-fit" role="tablist" aria-label="Skill trees">
        {trees.map((t) => (
          <button key={t} role="tab" aria-selected={t === active} onClick={() => setTree(t)}
            className={`px-3 py-1.5 rounded-[9px] text-sm ${t === active ? "bg-raised text-ink" : "text-ink-3 hover:text-ink"}`}>
            {t}
          </button>
        ))}
      </div>
      {inTree.length === 0 ? <EmptyState title="No skills in this tree" /> : (
        <ol className="grid gap-6">
          {tiers.map((tier) => (
            <li key={tier} className="grid gap-2">
              <h2 className="text-base text-ink-3 font-sans">{tier === 0 ? "Foundations" : `Builds on ${tier === 1 ? "foundations" : `step ${tier}`}`}</h2>
              <ul className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
                {inTree.filter((s) => s.tier === tier).map((s) => (
                  <li key={s.id}>
                    <button onClick={() => navigate(`/skills/${s.id}`)}
                      className={`w-full text-left px-4 py-3.5 grid gap-3 rounded-[14px] border transition-colors ${s.status === "DEMONSTRATED" ? "panel-reward" : s.status === "LOCKED" ? "border-line bg-transparent opacity-70 hover:opacity-100" : "panel hover:border-line-strong"}`}>
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-display text-lg leading-tight">{s.name}</span>
                        <span className={`chip ${s.status === "DEMONSTRATED" ? "text-gold-ink" : ""}`}>{STATUS_TEXT[s.status]}</span>
                      </div>
                      <Meter value={s.xp} max={s.xp_required} label="Practice XP" tone="gold" />
                      <Meter value={s.evidence_count} max={s.evidence_required} label="Evidence" tone="accent" />
                      {s.prerequisite_ids.length ? (
                        <p className="text-xs text-ink-3">Needs {s.prerequisite_ids.map((id) => byId.get(id)?.name ?? "a skill").join(" and ")}</p>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      )}
      <Dialog open={skillId !== undefined} title={byId.get(skillId ?? -1)?.name ?? "Skill"} onClose={() => navigate("/skills")}>
        {skillId !== undefined ? <SkillDetailView skillId={skillId} all={list.data.skills} /> : null}
      </Dialog>
      <Dialog open={creating} title="Add a skill" onClose={() => setCreating(false)}>
        <SkillForm trees={trees} defaultTree={active} onDone={() => setCreating(false)} />
      </Dialog>
    </div>
  );
}

function SkillDetailView({ skillId, all }: { skillId: number; all: Skill[] }) {
  const q = useQuery(`skills/${skillId}`, () => api.get<SkillDetail>(`/skills/${skillId}`));
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [prereq, setPrereq] = useState("");
  const addEvidence = useMutation(async () => {
    const r = await api.post<SkillDetail>(`/skills/${skillId}/evidence`, { title: title.trim(), url: url.trim() || null });
    setTitle("");
    setUrl("");
    for (const a of r.achievements_unlocked ?? []) toast({ tone: "reward", title: `Achievement: ${a.title}`, body: a.description });
    invalidate("skills", "achievements", "dashboard");
  });
  const removeEvidence = useMutation(async (id: number) => {
    await api.del(`/skills/${skillId}/evidence/${id}`);
    invalidate("skills");
  });
  const addPrereq = useMutation(async () => {
    await api.post(`/skills/${skillId}/prerequisites`, { prerequisite_id: Number(prereq) });
    setPrereq("");
    invalidate("skills");
  });
  const removePrereq = useMutation(async (id: number) => {
    await api.del(`/skills/${skillId}/prerequisites/${id}`);
    invalidate("skills");
  });
  const fields = addEvidence.error instanceof ApiError ? addEvidence.error.fieldErrors() : {};

  if (q.error) return <ErrorState error={q.error} onRetry={q.refetch} />;
  if (!q.data) return <Skeleton lines={4} />;
  const s = q.data;
  const names = new Map(all.map((x) => [x.id, x.name]));

  return (
    <div className="grid gap-5">
      <p className="text-ink-2">{s.tree}. Builds {humanize(s.attribute)}. Status: <span className="text-ink">{STATUS_TEXT[s.status]}</span>.</p>
      <div className="grid gap-3">
        <Meter value={s.xp} max={s.xp_required} label="Practice XP (from quests linked to this skill)" tone="gold" />
        <Meter value={s.evidence_count} max={s.evidence_required} label="Evidence of competency" tone="accent" />
      </div>

      <section className="grid gap-2">
        <h3>Evidence</h3>
        {s.evidence.length ? (
          <ul className="text-sm">
            {s.evidence.map((e) => (
              <li key={e.id} className="row py-2 flex items-center justify-between gap-3">
                <span className="min-w-0">
                  {e.url ? <a className="text-accent-ink hover:underline break-words" href={e.url} target="_blank" rel="noopener noreferrer">{e.title}</a> : <span>{e.title}</span>}
                  <span className="text-ink-3"> on {shortDay(e.created_at.slice(0, 10))}</span>
                </span>
                <button className="btn btn-ghost" onClick={() => removeEvidence.run(e.id)} aria-label={`Remove evidence ${e.title}`}>Remove</button>
              </li>
            ))}
          </ul>
        ) : <p className="text-sm text-ink-3">Nothing recorded yet. A query you wrote, a notebook, a dashboard or a passed test all count.</p>}
        <form className="grid sm:grid-cols-[1fr_1fr_auto] gap-2 items-end" onSubmit={(e: FormEvent) => { e.preventDefault(); addEvidence.run(); }}>
          <label className="field">What you made<input className="input" value={title} maxLength={120} onChange={(e: { target: { value: string } }) => setTitle(e.target.value)} placeholder="Customer churn query with joins" /></label>
          <label className="field">Link (optional)<input className="input" value={url} type="url" aria-invalid={Boolean(fields.url)} onChange={(e: { target: { value: string } }) => setUrl(e.target.value)} placeholder="https://github.com/…" /></label>
          <button className="btn btn-quiet min-h-10" disabled={!title.trim() || addEvidence.pending}>Add evidence</button>
        </form>
        {fields.url ? <p className="text-danger text-xs">{fields.url}</p> : <InlineError error={addEvidence.error} />}
      </section>

      <section className="grid gap-2">
        <h3>Prerequisites</h3>
        {s.prerequisite_ids.length ? (
          <ul className="flex flex-wrap gap-2">
            {s.prerequisite_ids.map((id) => (
              <li key={id} className="chip">
                {names.get(id) ?? `Skill ${id}`}
                <button className="text-ink-3 hover:text-ink" aria-label={`Remove prerequisite ${names.get(id)}`} onClick={() => removePrereq.run(id)}>✕</button>
              </li>
            ))}
          </ul>
        ) : <p className="text-sm text-ink-3">None. This is a foundation skill.</p>}
        <form className="flex gap-2" onSubmit={(e: FormEvent) => { e.preventDefault(); if (prereq) addPrereq.run(); }}>
          <select className="input" value={prereq} aria-label="Add prerequisite" onChange={(e: { target: { value: string } }) => setPrereq(e.target.value)}>
            <option value="">Choose a skill</option>
            {all.filter((x) => x.id !== s.id && !s.prerequisite_ids.includes(x.id)).map((x) => <option key={x.id} value={x.id}>{x.tree}: {x.name}</option>)}
          </select>
          <button className="btn btn-quiet" disabled={!prereq || addPrereq.pending}>Add</button>
        </form>
        <InlineError error={addPrereq.error ?? removePrereq.error ?? removeEvidence.error} />
      </section>
    </div>
  );
}

function SkillForm({ trees, defaultTree, onDone }: { trees: string[]; defaultTree: string; onDone: () => void }) {
  const [name, setName] = useState("");
  const [tree, setTree] = useState(defaultTree);
  const [xp, setXp] = useState("150");
  const [evidence, setEvidence] = useState("1");
  const save = useMutation(async () => api.post<SkillDetail>("/skills", { name: name.trim(), tree: tree.trim(), xp_required: Number(xp), evidence_required: Number(evidence) }));
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (await save.run()) {
      invalidate("skills");
      onDone();
    }
  }
  return (
    <form className="grid gap-4" onSubmit={submit}>
      <label className="field">Skill<input className="input" value={name} maxLength={60} autoFocus onChange={(e: { target: { value: string } }) => setName(e.target.value)} placeholder="Tableau" /></label>
      <label className="field">Tree<input className="input" list="trees" value={tree} maxLength={60} onChange={(e: { target: { value: string } }) => setTree(e.target.value)} /></label>
      <datalist id="trees">{trees.map((t) => <option key={t} value={t} />)}</datalist>
      <div className="grid grid-cols-2 gap-3">
        <label className="field">Practice XP needed<input className="input" type="number" min={0} value={xp} onChange={(e: { target: { value: string } }) => setXp(e.target.value)} /></label>
        <label className="field">Evidence needed<input className="input" type="number" min={0} max={50} value={evidence} onChange={(e: { target: { value: string } }) => setEvidence(e.target.value)} /></label>
      </div>
      <InlineError error={save.error} />
      <div className="flex justify-end"><button className="btn btn-primary" disabled={!name.trim() || !tree.trim() || save.pending}>Add skill</button></div>
    </form>
  );
}
