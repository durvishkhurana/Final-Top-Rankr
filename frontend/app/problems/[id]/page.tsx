"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { BoardTable } from "@/components/board-table";
import { ChallengerPanel } from "@/components/challenger-panel";
import { CodeEditor } from "@/components/code-editor";
import { LandscapePlayer } from "@/components/landscape-player";
import { SolutionView } from "@/components/solution-view";
import { ErrorNote, Loading } from "@/components/state";
import { SubmissionList } from "@/components/submission-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, post } from "@/lib/api";
import { useMe } from "@/lib/auth";
import type { Problem, ProblemView, Quota, Submission, Template } from "@/lib/types";

const selectClass = "h-8 rounded-lg border bg-background px-2 text-sm";

export default function ProblemPage() {
  const { id } = useParams<{ id: string }>();
  const me = useMe();
  const router = useRouter();
  const queryClient = useQueryClient();

  const problem = useQuery({
    queryKey: ["problem", id],
    queryFn: () => api<Problem>(`/problems/${id}`),
  });
  const templates = useQuery({
    queryKey: ["templates"],
    queryFn: () => api<Template[]>("/templates"),
    staleTime: Infinity,
  });
  const quota = useQuery({
    queryKey: ["quota", id],
    queryFn: () => api<Quota>(`/problems/${id}/quota`),
    enabled: !!me,
  });
  const mine = useQuery({
    queryKey: ["my-submissions", id],
    queryFn: () => api<Submission[]>(`/submissions?problem_id=${id}`),
    enabled: !!me,
  });

  // opened from a contest page: submissions are entered into that contest
  const search = useSearchParams();
  const contestId = search.get("contest") ? Number(search.get("contest")) : null;
  const [dim, setDim] = useState<number | undefined>(
    search.get("dim") ? Number(search.get("dim")) : undefined,
  );
  const [code, setCode] = useState<string>();
  const activeDim = dim ?? problem.data?.dims[0];
  const activeCode = code ?? templates.data?.[0]?.code ?? "";
  const kind = problem.data?.kind ?? "function";
  const view = useQuery({
    queryKey: ["view", id, activeDim, 1],
    queryFn: () => api<ProblemView>(`/problems/${id}/view?dim=${activeDim}`),
    enabled: kind !== "function" && !!activeDim,
  });

  // Count the cooldown down locally between quota fetches.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const wait = quota.data
    ? Math.max(0, Math.ceil(quota.data.wait_sec - (now - quota.dataUpdatedAt) / 1000))
    : 0;

  const submit = useMutation({
    mutationFn: () =>
      post<Submission>("/submissions", {
        problem_id: id,
        dim: activeDim,
        code: activeCode,
        contest_id: contestId,
      }),
    onSuccess: (sub) => {
      queryClient.invalidateQueries({ queryKey: ["quota", id] });
      queryClient.invalidateQueries({ queryKey: ["my-submissions", id] });
      router.push(`/submissions/${sub.id}`);
    },
  });

  if (problem.isPending) return <Loading />;
  if (problem.error) return <ErrorNote error={problem.error} />;
  const p = problem.data;
  const blocked = !quota.data || quota.data.remaining_today <= 0 || wait > 0;

  return (
    <div className="space-y-6">
      <div>
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link href="/problems" className="hover:underline">
            Problems
          </Link>
          / <span className="font-mono">{p.id}</span>
          <Badge variant="secondary">{p.level}</Badge>
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{p.name}</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6">{p.description}</p>
        <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 text-sm">
          <div>
            <dt className="text-muted-foreground">Search box</dt>
            <dd className="font-mono">
              [{-p.bound.toPrecision(4)}, {+p.bound.toPrecision(4)}] per variable
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Budget</dt>
            <dd>{activeDim ? (2000 * activeDim).toLocaleString() : "2000 × dimension"} evaluations</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Runs per submission</dt>
            <dd>3 instances × 5 seeds</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Tags</dt>
            <dd>{p.tags.join(", ")}</dd>
          </div>
        </dl>
      </div>

      {contestId && (
        <p role="status" className="rounded-lg border p-3 text-sm">
          Submissions from this page are entered into{" "}
          <Link href={`/contests/${contestId}`} className="underline">
            contest #{contestId}
          </Link>
          .
        </p>
      )}

      <div className="flex items-center gap-2 text-sm">
        <label htmlFor="dim">Dimension</label>
        <select
          id="dim"
          className={selectClass}
          value={activeDim}
          onChange={(e) => setDim(Number(e.target.value))}
        >
          {p.dims.map((d) => (
            <option key={d}>{d}</option>
          ))}
        </select>
      </div>

      {view.data && (
        <section>
          <h2 className="mb-2 text-lg font-medium">
            {kind === "landscape2d" ? "Landscape of public instance 1" : "Public instance 1"}
          </h2>
          {view.data.grid ? (
            <LandscapePlayer view={view.data} />
          ) : (
            view.data.data && <SolutionView kind={kind} data={view.data.data} />
          )}
        </section>
      )}

      <Tabs defaultValue="submit">
        <TabsList>
          <TabsTrigger value="submit">Submit</TabsTrigger>
          <TabsTrigger value="board">Leaderboard</TabsTrigger>
          <TabsTrigger value="mine">My submissions</TabsTrigger>
        </TabsList>

        <TabsContent value="submit" className="space-y-3 pt-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <label htmlFor="template">Start from</label>
            <select
              id="template"
              className={selectClass}
              defaultValue=""
              onChange={(e) => {
                const t = templates.data?.find((t) => t.key === e.target.value);
                if (t) setCode(t.code);
              }}
            >
              <option value="" disabled>
                a template…
              </option>
              {templates.data?.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.name}
                </option>
              ))}
            </select>
            <span className="text-muted-foreground">
              Define <code className="font-mono">optimize(f, dim, lower, upper, budget, rng)</code>.
              NumPy and SciPy are available.
            </span>
          </div>
          <CodeEditor value={activeCode} onChange={setCode} />
          {submit.error && <ErrorNote error={submit.error} />}
          <div className="flex flex-wrap items-center gap-3">
            {me ? (
              <>
                <Button onClick={() => submit.mutate()} disabled={blocked || submit.isPending}>
                  {submit.isPending
                    ? "Submitting…"
                    : wait > 0
                      ? `Wait ${wait}s`
                      : `Submit at dimension ${activeDim}`}
                </Button>
                {quota.data && (
                  <span className="text-sm text-muted-foreground" aria-live="polite">
                    {quota.data.remaining_today} of {quota.data.daily_cap} submissions left today
                    on this problem
                  </span>
                )}
              </>
            ) : (
              <p className="text-sm">
                <Link href="/login" className="underline">
                  Sign in
                </Link>{" "}
                to submit.
              </p>
            )}
          </div>
        </TabsContent>

        <TabsContent value="board" className="pt-3">
          {activeDim && (
            <>
              <BoardTable problemId={p.id} dim={activeDim} />
              <ChallengerPanel problemId={p.id} dim={activeDim} />
            </>
          )}
        </TabsContent>

        <TabsContent value="mine" className="pt-3">
          {!me ? (
            <p className="text-sm text-muted-foreground">Sign in to see your submissions.</p>
          ) : mine.isPending ? (
            <Loading />
          ) : mine.error ? (
            <ErrorNote error={mine.error} />
          ) : (
            <SubmissionList rows={mine.data} empty="You have not submitted to this problem yet." />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
