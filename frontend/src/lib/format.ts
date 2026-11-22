// Pure presentation helpers (unit-tested in tests/format.test.ts).
// No game rules live here: XP, levels and statuses always come from the server.

const nf = new Intl.NumberFormat("en-IN");

export function num(n: number): string {
  return nf.format(n);
}

export function signedXp(n: number): string {
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${num(Math.abs(n))} XP`;
}

export function pct(rate: number | null): string {
  return rate === null ? "Not enough data" : `${Math.round(rate * 100)}%`;
}

export function humanize(value: string): string {
  const s = value.replace(/_/g, " ").toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** Parse YYYY-MM-DD as a calendar date (no time-zone shifting). */
export function parseDay(day: string): { y: number; m: number; d: number; weekday: number } {
  const [y, m, d] = day.split("-").map(Number);
  const weekday = (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7; // 0 = Monday
  return { y, m, d, weekday };
}

export function shortDay(day: string): string {
  const { m, d } = parseDay(day);
  return `${d} ${MONTHS[m - 1]}`;
}

export function weekdayName(index: number): string {
  return DAYS[index];
}

export function addDays(day: string, n: number): string {
  const { y, m, d } = parseDay(day);
  const t = new Date(Date.UTC(y, m - 1, d + n));
  return t.toISOString().slice(0, 10);
}

/** Relative due-date wording, in calendar days from `today`. */
export function dueLabel(due: string | null, today: string): string | null {
  if (!due) return null;
  const diff = Math.round(
    (Date.UTC(...ymd(due)) - Date.UTC(...ymd(today))) / 86_400_000,
  );
  if (diff === 0) return "Due today";
  if (diff === 1) return "Due tomorrow";
  if (diff === -1) return "Was due yesterday";
  if (diff < 0) return `Was due ${shortDay(due)}`;
  if (diff < 7) return `Due ${DAYS[parseDay(due).weekday]}`;
  return `Due ${shortDay(due)}`;
}

function ymd(day: string): [number, number, number] {
  const { y, m, d } = parseDay(day);
  return [y, m - 1, d];
}

export const ACTION_LABELS: Record<string, string> = {
  publish: "Publish",
  start: "Start",
  pause: "Pause",
  resume: "Resume",
  complete: "Complete",
  reopen: "Reopen",
  cancel: "Cancel quest",
  expire: "Mark expired",
  restore: "Restore",
};

export const DIFFICULTY_PIPS: Record<string, number> = { EASY: 1, MEDIUM: 2, HARD: 3, EPIC: 4 };

export function streakLabel(n: number, unit: "day" | "week"): string {
  if (n === 0) return "No current streak";
  return `${n}-${unit} streak`;
}

export function avatarGlyph(avatar: string): string {
  const map: Record<string, string> = { sigil: "◈", spark: "✦", compass: "✣", orbit: "◎", crown: "♛", leaf: "❦" };
  return map[avatar] ?? "◈";
}
