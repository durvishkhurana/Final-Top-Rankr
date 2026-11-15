"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ErrorNote, Loading } from "@/components/state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, patch, post } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { Exam, Problem, Question } from "@/lib/types";

type Kit = { generators: Record<string, string>; facts: string[] };
const selectClass = "h-8 w-full rounded-lg border bg-background px-2 text-sm";
const lines = (s: string) =>
  s
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

function put<T>(path: string, body: unknown) {
  return api<T>(path, { method: "PUT", body: JSON.stringify(body) });
}

function QuestionForm({
  examId,
  kit,
  problems,
  onDone,
}: {
  examId: number;
  kit: Kit;
  problems: Problem[];
  onDone: () => void;
}) {
  const [kind, setKind] = useState<Question["kind"]>("mcq");
  const [generator, setGenerator] = useState(Object.keys(kit.generators)[0]);
  const [problemId, setProblemId] = useState(problems[0]?.id ?? "");
  const add = useMutation({
    mutationFn: (form: FormData) => {
      const data: Record<string, unknown> =
        kind === "mcq"
          ? { choices: lines(String(form.get("choices"))), correct: Number(form.get("correct")) - 1 }
          : kind === "numeric"
            ? { generator }
            : {
                problem_id: problemId,
                dim: Number(form.get("dim")),
                rubric: form.get("rubric"),
                follow_up: form.get("follow_up") === "on",
              };
      return post<Question>(`/tests/${examId}/questions`, {
        kind,
        prompt: form.get("prompt"),
        points: Number(form.get("points")),
        data,
      });
    },
    onSuccess: onDone,
  });
  const problem = problems.find((p) => p.id === problemId);
  return (
    <form
      key={kind + generator}
      className="space-y-3 rounded-xl border p-4"
      onSubmit={(e) => {
        e.preventDefault();
        add.mutate(new FormData(e.currentTarget));
      }}
    >
      <h2 className="font-medium">Add a question</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-1">
          <Label htmlFor="kind">Type</Label>
          <select id="kind" className={selectClass} value={kind} onChange={(e) => setKind(e.target.value as Question["kind"])}>
            <option value="mcq">Multiple choice</option>
            <option value="numeric">Numeric, personalised (answer computed by code)</option>
            <option value="reasoning">One-line reasoning about the student&apos;s own run</option>
          </select>
        </div>
        {kind === "numeric" && (
          <div className="space-y-1">
            <Label htmlFor="generator">Task</Label>
            <select id="generator" className={selectClass} value={generator} onChange={(e) => setGenerator(e.target.value)}>
              {Object.keys(kit.generators).map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </div>
        )}
        <div className="space-y-1">
          <Label htmlFor="points">Points</Label>
          <Input id="points" name="points" type="number" min={0.5} step={0.5} defaultValue={1} required />
        </div>
      </div>
      <div className="space-y-1">
        <Label htmlFor="prompt">Question</Label>
        <Textarea
          id="prompt"
          name="prompt"
          required
          rows={2}
          defaultValue={
            kind === "numeric"
              ? kit.generators[generator]
              : kind === "reasoning"
                ? "Your run stopped improving after {last_improvement_evals} of {budget} evaluations. In one line, why?"
                : ""
          }
        />
        {kind === "reasoning" && (
          <p className="text-xs text-muted-foreground">
            Placeholders filled with each student&apos;s own numbers: {kit.facts.map((f) => `{${f}}`).join(", ")}. The
            same text, with &quot;(no judged submission)&quot;, is shown to students who have none.
          </p>
        )}
      </div>
      {kind === "mcq" && (
        <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
          <div className="space-y-1">
            <Label htmlFor="choices">Choices, one per line</Label>
            <Textarea id="choices" name="choices" rows={4} required />
          </div>
          <div className="space-y-1">
            <Label htmlFor="correct">Correct line</Label>
            <Input id="correct" name="correct" type="number" min={1} defaultValue={1} required />
          </div>
        </div>
      )}
      {kind === "reasoning" && (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-1">
            <Label htmlFor="problem">About submissions to</Label>
            <select id="problem" className={selectClass} value={problemId} onChange={(e) => setProblemId(e.target.value)}>
              {problems.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id} {p.name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="dim">Dimension</Label>
            <select id="dim" name="dim" className={selectClass}>
              {problem?.dims.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </div>
          <label className="flex items-end gap-2 pb-1 text-sm">
            <input type="checkbox" name="follow_up" defaultChecked /> Ask one follow-up
          </label>
          <div className="space-y-1 sm:col-span-3">
            <Label htmlFor="rubric">Rubric for grading</Label>
            <Textarea id="rubric" name="rubric" rows={2} required />
          </div>
        </div>
      )}
      {add.error && <ErrorNote error={add.error} />}
      <Button type="submit" disabled={add.isPending}>
        Add question
      </Button>
    </form>
  );
}

function QuestionCard({ q, examId, draft, onChange }: { q: Question; examId: number; draft: boolean; onChange: () => void }) {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [pool, setPool] = useState((q.data.pool ?? []).join("\n"));
  const base = `/tests/${examId}/questions/${q.id}`;
  const done = { onSuccess: onChange };
  const remove = useMutation({ mutationFn: () => api(base, { method: "DELETE" }), ...done });
  const suggest = useMutation({
    mutationFn: () => post<{ distractors: string[] }>(`${base}/distractors`),
    onSuccess: (r) => setSuggestions(r.distractors),
  });
  const addChoice = useMutation({
    mutationFn: (choice: string) =>
      put(base, { kind: q.kind, prompt: q.prompt, points: q.points, data: { ...q.data, choices: [...(q.data.choices ?? []), choice] } }),
    onSuccess: (_, choice) => {
      setSuggestions((s) => s.filter((x) => x !== choice));
      onChange();
    },
  });
  const generate = useMutation({
    mutationFn: () => post<Question>(`${base}/pool`),
    onSuccess: (r) => {
      setPool((r.data.pool ?? []).join("\n"));
      onChange();
    },
  });
  const approve = useMutation({ mutationFn: () => post(`${base}/approve-pool`, { pool: lines(pool) }), ...done });
  const error = remove.error ?? suggest.error ?? addChoice.error ?? generate.error ?? approve.error;

  return (
    <li className="space-y-2 rounded-xl border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">Q{q.position}</span>
        <Badge variant="outline">{q.kind}</Badge>
        <span className="text-sm text-muted-foreground">
          {q.points} point{q.points === 1 ? "" : "s"}
        </span>
        {draft && (
          <Button variant="ghost" size="sm" className="ml-auto" onClick={() => remove.mutate()}>
            Delete
          </Button>
        )}
      </div>
      <p className="text-sm">{q.prompt}</p>
      {q.kind === "mcq" && (
        <>
          <ol className="list-decimal pl-6 text-sm">
            {q.data.choices?.map((c, i) => (
              <li key={i} className={i === q.data.correct ? "font-medium" : ""}>
                {c} {i === q.data.correct && "(correct)"}
              </li>
            ))}
          </ol>
          {draft && (
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" disabled={suggest.isPending} onClick={() => suggest.mutate()}>
                {suggest.isPending ? "Asking…" : "Suggest distractors (AI)"}
              </Button>
              {suggestions.map((s) => (
                <Button key={s} variant="secondary" size="sm" onClick={() => addChoice.mutate(s)}>
                  + {s}
                </Button>
              ))}
            </div>
          )}
        </>
      )}
      {q.kind === "numeric" && <p className="text-xs text-muted-foreground">Task: {q.data.generator}. Each student gets their own numbers.</p>}
      {q.kind === "reasoning" && (
        <div className="space-y-2 text-sm">
          <p className="text-muted-foreground">
            About {q.data.problem_id} at dimension {q.data.dim}. Rubric: {q.data.rubric}
            {q.data.follow_up && " · one follow-up"}
          </p>
          <div className="flex items-center gap-2">
            <span className="font-medium">Phrasings</span>
            {q.pool_approved ? <Badge variant="secondary">approved</Badge> : <Badge variant="outline">not approved</Badge>}
          </div>
          {draft ? (
            <>
              <Textarea
                aria-label={`Phrasings of question ${q.position}, one per line`}
                rows={6}
                value={pool}
                onChange={(e) => setPool(e.target.value)}
                placeholder="One phrasing per line, or generate a pool with AI"
              />
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={generate.isPending} onClick={() => generate.mutate()}>
                  {generate.isPending ? "Generating…" : "Generate 20 phrasings (AI)"}
                </Button>
                <Button size="sm" disabled={!pool.trim() || approve.isPending} onClick={() => approve.mutate()}>
                  Approve these phrasings
                </Button>
              </div>
            </>
          ) : (
            <ul className="list-disc pl-6">
              {q.data.pool?.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {error && <ErrorNote error={error} />}
    </li>
  );
}

export default function EditTestPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const exam = useQuery({ queryKey: ["test", id], queryFn: () => api<Exam>(`/tests/${id}`) });
  const questions = useQuery({ queryKey: ["questions", id], queryFn: () => api<Question[]>(`/tests/${id}/questions`) });
  const kit = useQuery({ queryKey: ["question-kit"], queryFn: () => api<Kit>("/tests/question-kit") });
  const problems = useQuery({ queryKey: ["problems"], queryFn: () => api<Problem[]>("/problems") });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["test", id] });
    queryClient.invalidateQueries({ queryKey: ["questions", id] });
  };
  const status = useMutation({
    mutationFn: (s: Exam["status"]) => patch<Exam>(`/tests/${id}`, { status: s }),
    onSettled: refresh,
  });

  if (exam.isPending || questions.isPending || kit.isPending || problems.isPending) return <Loading />;
  const error = exam.error ?? questions.error ?? kit.error ?? problems.error;
  if (error) return <ErrorNote error={error} />;
  const t = exam.data!;
  const draft = t.status === "draft";

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-muted-foreground">
          <Link href="/tests" className="hover:underline">
            Tests
          </Link>{" "}
          / {t.course_title}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{t.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {fmtDate(t.starts_at)} to {fmtDate(t.ends_at)} · camera checks {t.camera_checks ? "offered" : "off"} ·{" "}
          {t.max_total} points
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{t.status}</Badge>
        {draft && (
          <Button size="sm" disabled={status.isPending} onClick={() => status.mutate("live")}>
            Publish
          </Button>
        )}
        {t.status === "live" && (
          <Button size="sm" variant="outline" disabled={status.isPending} onClick={() => status.mutate("closed")}>
            Close and grade open attempts
          </Button>
        )}
        <Link href={`/tests/${id}/results`} className="text-sm underline">
          Results
        </Link>
      </div>
      {status.error && <ErrorNote error={status.error} />}
      {!draft && <p className="text-sm text-muted-foreground">Questions are locked once a test is published.</p>}
      <ul className="space-y-3">
        {questions.data!.map((q) => (
          <QuestionCard key={q.id} q={q} examId={t.id} draft={draft} onChange={refresh} />
        ))}
      </ul>
      {draft && <QuestionForm examId={t.id} kit={kit.data!} problems={problems.data!} onDone={refresh} />}
    </div>
  );
}
