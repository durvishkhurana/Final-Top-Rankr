// Mirrors backend/api/schemas.py

export type Role = "student" | "instructor" | "admin";

export interface Me {
  id: number;
  email: string;
  name: string;
  role: Role;
  country: string;
  institution: string;
  bio: string;
}

export interface Problem {
  id: string;
  name: string;
  category: string;
  level: string;
  tags: string[];
  summary: string;
  dims: number[];
  bound: number;
  is_active: boolean;
  submissions: number;
  description?: string;
}

export interface Quota {
  daily_cap: number;
  used_today: number;
  remaining_today: number;
  cooldown_sec: number;
  wait_sec: number;
}

export interface BoardRow {
  rank: number;
  user_id: number;
  name: string;
  country: string;
  institution: string;
  is_baseline: boolean;
  submission_id: number;
  score: number;
  median_precision: number | null;
  iqr: number | null;
  submitted_at: string;
}

export interface Template {
  key: string;
  name: string;
  code: string;
}

export interface Run {
  instance_seed: number;
  seed: number;
  status: string;
  error: string;
  evals: number;
  aocc: number;
  precision: number | null;
  wall_sec: number;
  precision_trace: (number | null)[];
  log: string;
}

export interface Submission {
  id: number;
  user_id: number;
  user_name: string;
  problem_id: string;
  dim: number;
  status: "queued" | "running" | "done" | "failed";
  error: string;
  budget: number | null;
  score: number | null;
  aocc: number | null;
  iqr: number | null;
  median_precision: number | null;
  created_at: string;
  finished_at: string | null;
}

export interface SubmissionDetail extends Submission {
  code: string;
  checkpoints: number[];
  runs: Run[];
}

export interface GlobalRow {
  rank: number;
  key: string;
  name: string;
  country: string;
  institution: string;
  rating: number;
  problems: number;
  members: number;
}

export interface Stats {
  users: number;
  problems: number;
  submissions: number;
  runs: number;
  evaluations: number;
  per_day: { day: string; count: number }[];
  per_problem: { problem_id: string; name: string; count: number }[];
  by_status: Record<string, number>;
}

export interface Profile {
  id: number;
  name: string;
  role: Role;
  country: string;
  institution: string;
  bio: string;
  created_at: string;
  rating: number;
  rank: number | null;
  problems_attempted: number;
  submissions: number;
  recent: Pick<Submission, "id" | "problem_id" | "dim" | "status" | "score" | "created_at">[];
}

export interface AdminUser {
  id: number;
  email: string;
  name: string;
  role: Role;
  is_bot: boolean;
  is_demo: boolean;
  created_at: string;
}
