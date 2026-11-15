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
  kind: "function" | "landscape2d" | "timetable" | "facility" | "routing";
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
  points: [number, number][] | null;
  solution: Solution | null;
}

export interface Curve {
  label: string;
  is_baseline: boolean;
  submission_id: number;
  median: (number | null)[];
}

export interface Curves {
  checkpoints: number[];
  curves: Curve[];
}

export interface ProblemView {
  kind: Problem["kind"];
  lower: number[];
  upper: number[];
  grid: number[][] | null;
  data: InstanceData | null;
}

type XY = { x: number; y: number };

// Public instance data of the real-world packs (backend/judge/realworld.py: public())
export interface InstanceData {
  size?: number;
  // timetable
  courses?: { name: string; students: number }[];
  rooms?: number[];
  slots?: number;
  clash_pairs?: number;
  // facility
  stops?: number;
  demand?: (XY & { people: number })[];
  // routing
  capacity?: number;
  depot?: XY;
  customers?: (XY & { demand: number })[];
}

// Decoded best solution of a run (decode())
export interface Solution {
  slots?: { course: string; students: number; room: number | null; capacity: number }[][];
  clashing_students?: number;
  unseated_students?: number;
  stops?: (XY & { people: number })[];
  assigned?: number[];
  mean_distance?: number;
  routes?: { customers: number[]; load: number }[];
  total_distance?: number;
}

export interface Submission {
  id: number;
  user_id: number;
  user_name: string;
  problem_id: string;
  dim: number;
  contest_id: number | null;
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

export interface Contest {
  id: number;
  title: string;
  description: string;
  tasks: { problem_id: string; dim: number }[];
  starts_at: string;
  ends_at: string;
  phase: "upcoming" | "running" | "ended" | "finalising" | "final";
  invite_only: boolean;
  course_id: number | null;
  hint_level: "off" | "concept" | "specific";
  participants: number;
  joined: boolean;
  can_manage: boolean;
  invite_code: string | null;
}

export interface ContestBoardRow {
  rank: number;
  user_id: number;
  name: string;
  is_baseline: boolean;
  total: number;
  scores: Record<string, number>;
  final: boolean;
}

export interface Course {
  id: number;
  title: string;
  description: string;
  instructor: string;
  students: number;
  teaches: boolean;
  invite_code: string | null;
}

export interface Dashboard {
  course: Course;
  columns: { key: string; contest: string; contest_id: number; problem_id: string; dim: number }[];
  students: {
    user_id: number;
    name: string;
    email: string;
    scores: Record<string, number | null>;
    submissions: number;
    last_active: string | null;
  }[];
}

export interface AiStatus {
  enabled: boolean;
  remaining_today: number;
}

export interface AiNote {
  kind: "analysis" | "coach";
  content: Record<string, string | boolean>;
  created_at: string;
}

export interface Contribution {
  id: number;
  user_id: number;
  name: string;
  summary: string;
  description: string;
  source: string;
  lower: number;
  upper: number;
  dims: number[];
  level: string;
  tags: string[];
  ai_built: boolean;
  status: "testing" | "failed" | "pending" | "approved" | "rejected";
  smoke: { ok: boolean; checks: { name: string; ok: boolean; detail: string }[] } | null;
  problem_id: string | null;
  created_at: string;
}
