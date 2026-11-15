"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Empty, ErrorNote, Loading } from "@/components/state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, post } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { AnswerResult, AttemptResult, Exam } from "@/lib/types";

const EVENT_TEXT: Record<string, string> = {
  tab_hidden: "switched away from the tab",
  window_blur: "left the window",
  fullscreen_exit: "left full screen",
  copy: "copied",
  paste: "pasted",
  no_face: "no face visible",
  multiple_faces: "more than one face visible",
  head_turned: "looked away",
  camera_unavailable: "camera checks could not start",
};

const secs = (ms: number) => (ms >= 1000 ? `${Math.round(ms / 1000)} s` : "");

function Override({ a, onDone }: { a: AnswerResult; onDone: () => void }) {
  const [score, setScore] = useState(String(a.score ?? ""));
  const [reason, setReason] = useState("");
  const save = useMutation({
    mutationFn: () => post(`/answers/${a.id}/grade`, { score: Number(score), reason }),
    onSuccess: () => {
      setReason("");
      onDone();
    },
  });
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <Input
        aria-label="New score"
        type="number"
        min={0}
        max={a.max_score}
        step={0.5}
        value={score}
        onChange={(e) => setScore(e.target.value)}
        className="w-20"
        required
      />
      <Input aria-label="Reason for the change" placeholder="Reason (kept in the log)" value={reason} onChange={(e) => setReason(e.target.value)} className="w-64" required />
      <Button type="submit" size="sm" variant="outline" disabled={save.isPending}>
        Set grade
      </Button>
      {save.error && <ErrorNote error={save.error} />}
    </form>
  );
}

function Student({ r, onChange }: { r: AttemptResult; onChange: () => void }) {
  const viva = useMutation({ mutationFn: () => post<string[]>(`/attempts/${r.id}/viva`), onSuccess: onChange });
  const flagged = r.answers.reduce((n, a) => n + a.flags.length, 0) + r.events.length;
  return (
    <details className="rounded-xl border p-4">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2">
        <span className="font-medium">{r.name}</span>
        <Badge variant="outline">{r.status.replace("_", " ")}</Badge>
        <span className="text-sm tabular-nums">{r.total != null ? `${r.total} points` : "not graded"}</span>
        {flagged > 0 && <Badge variant="secondary">{flagged} signals to review</Badge>}
      </summary>
      <div className="mt-4 space-y-5 text-sm">
        <p className="text-muted-foreground">
          Started {fmtDate(r.started_at)}
          {r.submitted_at && ` · handed in ${fmtDate(r.submitted_at)}`} · camera checks{" "}
          {r.camera_consent ? "allowed" : "not used"}
        </p>
        <ol className="space-y-4">
          {r.answers.map((a) => (
            <li key={a.id} className="space-y-1 border-l-2 pl-3">
              <p className="font-medium">{a.prompt}</p>
              <p>
                Answer: <span className="whitespace-pre-wrap">{a.response || "(none)"}</span>
                {a.correct != null && <span className="text-muted-foreground"> · correct: {a.correct}</span>}
              </p>
              {a.follow_up && (
                <p>
                  Follow-up: {a.follow_up} <br />
                  Answer: {a.follow_up_response || "(none)"}
                </p>
              )}
              <p className="tabular-nums">
                Score {a.score ?? "–"} / {a.max_score}
                {a.graded_by && ` · ${a.graded_by === "ai" ? "AI-assisted grade" : `graded by ${a.graded_by}`}`}
                {a.confidence != null && ` · confidence ${Math.round(a.confidence * 100)}%`}
                {` · ${secs(a.time_ms) || "<1 s"} on this answer`}
                {a.paste_chars > 0 && ` · ${a.paste_chars} characters pasted`}
                {a.submission_id && (
                  <>
                    {" · "}
                    <Link href={`/submissions/${a.submission_id}`} className="underline">
                      run asked about
                    </Link>
                  </>
                )}
              </p>
              {a.rationale && <p className="text-muted-foreground">{a.rationale}</p>}
              {a.flags.map((f) => (
                <p key={f} className="text-amber-700 dark:text-amber-400">
                  Flag: {f}
                </p>
              ))}
              <Override a={a} onDone={onChange} />
              {a.history.length > 0 && (
                <details className="text-xs text-muted-foreground">
                  <summary className="cursor-pointer">Grade history</summary>
                  <ul className="mt-1 space-y-0.5">
                    {a.history.map((h, i) => (
                      <li key={i}>
                        {fmtDate(h.created_at)} · {h.actor}: {h.old_score ?? "–"} → {h.new_score ?? "–"} ({h.reason})
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </li>
          ))}
        </ol>
        <section>
          <h3 className="mb-1 font-medium">Signal timeline</h3>
          {r.events.length === 0 ? (
            <p className="text-muted-foreground">No signals recorded.</p>
          ) : (
            <ul className="space-y-0.5">
              {r.events.map((e, i) => (
                <li key={i} className="tabular-nums">
                  {new Date(e.at).toLocaleTimeString()} · {EVENT_TEXT[e.kind] ?? e.kind}
                  {e.duration_ms > 0 && ` for ${secs(e.duration_ms)}`}
                  {e.detail && ` (${e.detail})`}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-1 text-xs text-muted-foreground">Signals are prompts for a conversation, not evidence. Nothing is failed automatically.</p>
        </section>
        <section>
          <h3 className="mb-1 font-medium">Viva questions (only you see these)</h3>
          {r.viva ? (
            <ol className="list-decimal space-y-1 pl-6">
              {r.viva.map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ol>
          ) : (
            <Button variant="outline" size="sm" disabled={viva.isPending} onClick={() => viva.mutate()}>
              {viva.isPending ? "Generating…" : "Generate 3 viva questions from their code (AI)"}
            </Button>
          )}
          {viva.error && <ErrorNote error={viva.error} />}
        </section>
      </div>
    </details>
  );
}

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const exam = useQuery({ queryKey: ["test", id], queryFn: () => api<Exam>(`/tests/${id}`) });
  const results = useQuery({
    queryKey: ["results", id],
    queryFn: () => api<AttemptResult[]>(`/tests/${id}/results`),
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "submitted") ? 3000 : false),
  });
  if (exam.isPending || results.isPending) return <Loading />;
  if (exam.error ?? results.error) return <ErrorNote error={exam.error ?? results.error} />;
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["results", id] });

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-muted-foreground">
          <Link href={`/tests/${id}/edit`} className="hover:underline">
            {exam.data!.title}
          </Link>{" "}
          / results
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Results</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Multiple-choice and numeric answers are graded by code. Reasoning answers get an AI-assisted grade against your
          rubric; you can change any grade, and every change is logged.
        </p>
      </div>
      {results.data!.length === 0 ? (
        <Empty>No attempts yet.</Empty>
      ) : (
        <div className="space-y-3">
          {results.data!.map((r) => (
            <Student key={r.id} r={r} onChange={refresh} />
          ))}
        </div>
      )}
    </div>
  );
}
