// API response types — mirror backend/lifeexe/api/schemas.py.

export interface Progress {
  level: number;
  total_xp: number;
  level_floor_xp: number;
  next_level_xp: number;
  xp_into_level: number;
  xp_span: number;
  xp_to_next_level: number;
  progress_ratio: number;
}

export type QuestStatus = "DRAFT" | "AVAILABLE" | "ACTIVE" | "PAUSED" | "COMPLETED" | "CANCELLED" | "EXPIRED";
export type Difficulty = "EASY" | "MEDIUM" | "HARD" | "EPIC";
export type Priority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type Category = "MAIN" | "SIDE" | "DAILY" | "WEEKLY" | "MILESTONE" | "CHALLENGE" | "BOSS";
export type Recurrence = "NONE" | "DAILY" | "WEEKLY";
export type QuestAction = "publish" | "start" | "pause" | "resume" | "complete" | "reopen" | "cancel" | "expire" | "restore";

export interface Quest {
  id: number;
  title: string;
  description: string;
  category: Category;
  priority: Priority;
  difficulty: Difficulty;
  status: QuestStatus;
  recurrence: Recurrence;
  estimated_minutes: number | null;
  due_date: string | null;
  completion_criteria: string;
  skill: { id: number; name: string; attribute: string } | null;
  xp_reward: number;
  coin_reward: number;
  occurrence_completed: boolean;
  completion_count: number;
  overdue: boolean;
  archived: boolean;
  allowed_actions: QuestAction[];
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  history?: { id: number; occurrence_key: string; local_date: string; completed_at: string; reversed_at: string | null; xp_awarded: number }[] | null;
}

export interface QuestList { items: Quest[]; total: number; limit: number; offset: number }

export interface AchievementBrief { key: string; title: string; description: string }

export interface CompletionResult {
  quest: Quest;
  reward: { xp_awarded: number; base_xp: number; coins_awarded: number; capped: boolean; daily_cap: number; occurrence_key: string };
  progress: Progress;
  level_before: number;
  leveled_up: boolean;
  achievements_unlocked: AchievementBrief[];
}

export interface ReopenResult { quest: Quest; xp_reversed: number; progress: Progress; level_before: number }

export type DayState = "DONE" | "PARTIAL" | "REST" | "PAUSED" | "MISSED" | "PENDING" | "OPEN" | "NOT_SCHEDULED" | "BEFORE_START";

export interface Habit {
  id: number;
  name: string;
  description: string;
  schedule_kind: "DAILY" | "WEEKDAYS" | "WEEKLY_COUNT";
  weekdays: number[];
  target_per_week: number | null;
  measure: "BOOLEAN" | "COUNT" | "DURATION";
  target_value: number;
  attribute: string;
  start_date: string;
  archived: boolean;
  paused: boolean;
  scheduled_today: boolean;
  today: { state: DayState; value: number; entry_type: "ENTRY" | "REST" | null };
  stats: {
    unit: "day" | "week";
    current_streak: number;
    longest_streak: number;
    total_done: number;
    week_progress: [number, number] | null;
    windows: { label: string; achieved: number; required: number; rate: number | null }[];
  };
  calendar: { date: string; state: DayState; value: number }[];
}

export interface HabitLogResult { habit: Habit; xp_delta: number; progress: Progress; achievements_unlocked: AchievementBrief[] }

export interface Skill {
  id: number;
  slug: string;
  name: string;
  tree: string;
  attribute: string;
  description: string;
  xp: number;
  xp_required: number;
  evidence_count: number;
  evidence_required: number;
  status: "LOCKED" | "AVAILABLE" | "IN_PROGRESS" | "DEMONSTRATED";
  prerequisite_ids: number[];
  tier: number;
  roadmap_position: number;
}

export interface SkillDetail extends Skill {
  evidence: { id: number; title: string; url: string | null; notes: string; created_at: string }[];
  achievements_unlocked?: AchievementBrief[];
}

export interface Profile {
  user_id: number;
  today: string;
  email: string;
  display_name: string;
  title: string;
  avatar: string;
  theme: string;
  timezone: string;
  day_start_hour: number;
  account_created_at: string;
  progress: Progress;
  coins: number;
  attributes: { attribute: string; xp: number; rank: number }[];
  options: {
    titles: { title: string; unlock_level: number; unlocked: boolean }[];
    unlocked_titles: string[];
    avatars: string[];
    themes: string[];
  };
  game: { xp_by_difficulty: Record<Difficulty, number>; habit_checkin_xp: number; daily_xp_cap: number; coin_divisor: number };
}

export interface Dashboard {
  today: string;
  character: { display_name: string; title: string; avatar: string; progress: Progress; coins: number };
  priorities: Quest[];
  today_quests: Quest[];
  habits: Habit[];
  week: { start: string; net_xp: number; quest_completions: number; habit_days: number; xp_today: number; daily_xp_cap: number };
  recent_achievements: { key: string; title: string; description: string; unlocked_at: string }[];
  recent_xp: { id: number; amount: number; reason: string; local_date: string; created_at: string; label: string }[];
}

export interface Point { date: string; value: number }

export interface Analytics {
  range: { from: string; to: string; days: number; timezone: string; day_start_hour: number };
  totals: { net_xp: number; quest_completions: number; habit_days: number; active_days: number };
  series: { net_xp: Point[]; quest_completions: Point[]; habit_days: Point[]; activity: Point[] };
  xp_by_attribute: { attribute: string; xp: number }[];
  xp_by_skill: { skill_id: number; name: string; tree: string; xp: number }[];
  completions_by_category: { category: string; count: number }[];
  weekly: {
    this_week_start: string;
    completions_this_week: number;
    completions_last_week: number;
    completion_rate_this_week: { completed: number; counted: number; rate: number | null };
    completion_rate_last_week: { completed: number; counted: number; rate: number | null };
  };
  insights: { kind: string; text: string; basis: Record<string, number | string> }[];
  definitions: Record<string, string>;
}

export interface Achievement {
  key: string;
  title: string;
  description: string;
  category: string;
  hidden: boolean;
  unlocked: boolean;
  unlocked_at: string | null;
}
