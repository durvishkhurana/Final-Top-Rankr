"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AiNotes } from "@/components/ai-notes";
import { CodeEditor } from "@/components/code-editor";
import { ConvergenceChart } from "@/components/convergence-chart";
import { Downloads } from "@/components/downloads";
import { LandscapePlayer } from "@/components/landscape-player";
import { SolutionView } from "@/components/solution-view";
import { ErrorNote, Loading } from "@/components/state";
import { StatusBadge } from "@/components/submission-list";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fmtDate, fmtPrecision, fmtScore } from "@/lib/format";
import type { Curves, Problem, ProblemView, SubmissionDetail } from "@/lib/types";
import { selectClass } from "@/lib/utils";

export default function SubmissionPage() {
  const { id } = useParams<{ id: string }>();
  const { data: sub, error, isPending } = useQuery({
    queryKey: ["submission", id],
    queryFn: () => api<SubmissionDetail>(`/submissions/${id}`),
    // poll while the judge is working
    refetchInterval: (q) =>
      q.state.data && ["queued", "running"].includes(q.state.data.status) ? 1500 : false,
  });

  const done = sub?.status === "done";
  const problem = useQuery({
    queryKey: ["problem", sub?.problem_id],
    queryFn: () => api<Problem>(`/problems/${sub!.problem_id}`),
    enabled: !!sub,
  });
  const curves = useQuery({
    queryKey: ["curves", sub?.problem_id, sub?.dim],
    queryFn: () => api<Curves>(`/problems/${sub!.problem_id}/curves?dim=${sub!.dim}`),
    enabled: done,
  });
  // which run to show in the landscape / solution panel: "instance-seed"
  const [picked, setPicked] = useState<string>();
  const run = sub?.runs.find((r) => `${r.instance_seed}-${r.seed}` === picked) ?? sub?.runs[0];
  const kind = problem.data?.kind ?? "function";
  const view = useQuery({
    queryKey: ["view", sub?.problem_id, sub?.dim, run?.instance_seed],
    queryFn: () =>
      api<ProblemView>(
        `/problems/${sub!.problem_id}/view?dim=${sub!.dim}&instance_seed=${run!.instance_seed}`,
      ),
    enabled: done && kind !== "function" && !!run,
  });

  if (isPending) return <Loading />;
  if (error) return <ErrorNote error={error} />;

  const working = sub.status === "queued" || sub.status === "running";
  const failedRun = sub.runs.find((r) => r.status !== "ok" && r.error);
  const log = sub.runs.find((r) => r.log)?.log;
  const figures = [
    ["Score", `${fmtScore(sub.score)} / 1000`],
    ["Median precision", fmtPrecision(sub.median_precision)],
    ["IQR across seeds", sub.iqr?.toFixed(3) ?? "–"],
    ["Budget per run", sub.budget ? `${sub.budget.toLocaleString()} evaluations` : "–"],
  ];

  return (
    <div className="space-y-8">
      <div>
        <p className="text-sm text-muted-foreground">
          <Link href={`/problems/${sub.problem_id}`} className="hover:underline">
            <span className="font-mono">{sub.problem_id}</span>
          </Link>{" "}
          · dimension {sub.dim} · by{" "}
          <Link href={`/profile/${sub.user_id}`} className="hover:underline">
            {sub.user_name}
          </Link>{" "}
          · {fmtDate(sub.created_at)}
        </p>
        <h1 className="mt-1 flex items-center gap-3 text-2xl font-semibold tracking-tight">
          Submission #{sub.id} <StatusBadge status={sub.status} />
        </h1>
      </div>

      {working && (
        <p role="status" className="rounded-lg border p-4 text-sm">
          {sub.status === "queued" ? "Waiting for a judge…" : "Running 15 runs in the sandbox…"}{" "}
          This page updates by itself.
        </p>
      )}
      {sub.status === "failed" && <ErrorNote error={new Error(sub.error || "Judging failed.")} />}

      {sub.status === "done" && (
        <>
          <section aria-label="Result" className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {figures.map(([label, value]) => (
              <div key={label} className="rounded-xl border p-4">
                <div className="text-xl font-semibold tabular-nums">{value}</div>
                <div className="text-sm text-muted-foreground">{label}</div>
              </div>
            ))}
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium">Convergence</h2>
            <ConvergenceChart
              checkpoints={sub.checkpoints}
              runs={sub.runs}
              overlays={curves.data?.curves.filter((c) => c.submission_id !== sub.id)}
            />
          </section>

          {kind !== "function" && run && (
            <section>
              <h2 className="mb-2 text-lg font-medium">
                {kind === "landscape2d" ? "Search replay" : "Best solution found"}
              </h2>
              <div className="mb-3 flex items-center gap-2 text-sm">
                <label htmlFor="run">Run</label>
                <select
                  id="run"
                  className={selectClass}
                  value={`${run.instance_seed}-${run.seed}`}
                  onChange={(e) => setPicked(e.target.value)}
                >
                  {sub.runs.map((r) => (
                    <option key={`${r.instance_seed}-${r.seed}`} value={`${r.instance_seed}-${r.seed}`}>
                      instance {r.instance_seed}, seed {r.seed}
                    </option>
                  ))}
                </select>
              </div>
              {view.isPending && <Loading rows={2} />}
              {view.error && <ErrorNote error={view.error} />}
              {view.data?.grid && run.points && (
                <LandscapePlayer
                  key={`${run.instance_seed}-${run.seed}`}
                  view={view.data}
                  points={run.points}
                />
              )}
              {view.data?.data &&
                (run.solution ? (
                  <SolutionView kind={kind} data={view.data.data} solution={run.solution} />
                ) : (
                  <p className="text-sm text-muted-foreground">This run produced no solution.</p>
                ))}
            </section>
          )}

          {failedRun && (
            <section>
              <h2 className="mb-2 text-lg font-medium">First error</h2>
              <pre className="overflow-x-auto rounded-lg border bg-muted p-3 text-xs">
                {failedRun.error}
              </pre>
            </section>
          )}

          <section>
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-lg font-medium">Runs</h2>
              <Downloads path={`/submissions/${sub.id}/export`} label="Runs with convergence:" />
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Instance</TableHead>
                  <TableHead>Seed</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Evaluations</TableHead>
                  <TableHead className="text-right">Final precision</TableHead>
                  <TableHead className="text-right">AOCC</TableHead>
                  <TableHead className="text-right">Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sub.runs.map((r) => (
                  <TableRow key={`${r.instance_seed}-${r.seed}`}>
                    <TableCell>{r.instance_seed}</TableCell>
                    <TableCell>{r.seed}</TableCell>
                    <TableCell>
                      <StatusBadge status={r.status} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.evals.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmtPrecision(r.precision)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{r.aocc.toFixed(3)}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.wall_sec.toFixed(1)} s
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </section>
        </>
      )}

      {log && (
        <section>
          <h2 className="mb-2 text-lg font-medium">Output of the first run that printed</h2>
          <pre className="max-h-64 overflow-auto rounded-lg border bg-muted p-3 text-xs">{log}</pre>
        </section>
      )}

      {sub.code && (
        <section>
          <h2 className="mb-2 text-lg font-medium">Code</h2>
          <CodeEditor value={sub.code} readOnly height={360} />
        </section>
      )}

      {sub.code && (
        <section>
          <h2 className="mb-2 text-lg font-medium">AI feedback</h2>
          <AiNotes submissionId={sub.id} judged={done} />
        </section>
      )}
    </div>
  );
}
