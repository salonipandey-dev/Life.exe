// Pure form <-> API mapping for quests (unit-tested).
import type { Category, Difficulty, Priority, Quest, Recurrence } from "./types";

export interface QuestDraft {
  title: string;
  description: string;
  category: Category;
  priority: Priority;
  difficulty: Difficulty;
  recurrence: Recurrence;
  estimated_minutes: string;
  due_date: string;
  completion_criteria: string;
  skill_id: string;
}

export function draftFrom(q?: Quest): QuestDraft {
  return {
    title: q?.title ?? "",
    description: q?.description ?? "",
    category: q?.category ?? "SIDE",
    priority: q?.priority ?? "MEDIUM",
    difficulty: q?.difficulty ?? "MEDIUM",
    recurrence: q?.recurrence ?? "NONE",
    estimated_minutes: q?.estimated_minutes ? String(q.estimated_minutes) : "",
    due_date: q?.due_date ?? "",
    completion_criteria: q?.completion_criteria ?? "",
    skill_id: q?.skill ? String(q.skill.id) : "",
  };
}

/** Convert form state into an API payload. XP is never part of it. */
export function toPayload(d: QuestDraft): Record<string, unknown> {
  return {
    title: d.title.trim(),
    description: d.description.trim(),
    category: d.category,
    priority: d.priority,
    difficulty: d.difficulty,
    recurrence: d.recurrence,
    estimated_minutes: d.estimated_minutes ? Number(d.estimated_minutes) : null,
    due_date: d.recurrence === "NONE" && d.due_date ? d.due_date : null,
    completion_criteria: d.completion_criteria.trim(),
    skill_id: d.skill_id ? Number(d.skill_id) : null,
  };
}

