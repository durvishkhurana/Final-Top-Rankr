"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Downloads } from "@/components/downloads";
import { ProblemPicker, useProblems } from "@/components/problem-picker";
import { PALETTE } from "@/components/solution-view";
import { Empty, ErrorNote, Loading, PageTitle } from "@/components/state";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, post } from "@/lib/api";
import { evalTicks, fmtScore } from "@/lib/format";
import type { BoardRow, Comparison } from "@/lib/types";

const MAX = 8;

const fmtP = (p: number) => (p < 0.001 ? "< 0.001" : p.toFixed(3));

/** Default selection: the top three people and every baseline. */
function defaults(board: BoardRow[]): number[] {
  const people = board.filter((r) => !r.is_baseline).slice(0, 3);
  return [...people, ...board.filter((r) => r.is_baseline)].slice(0, MAX).map((r) => r.submission_id);
}

function Ecdf({ data }: { data: Comparison }) {
  const rows = data.checkpoints.map((evals, k) => ({
    evals,
    ...Object.fromEntries(data.entries.map((e) => [e.submission_id, e.ecdf[k]])),
  }));
  return (
    <figure>
      <div className="h-72 w-full">
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 16, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis
              dataKey="evals"
              type="number"
              scale="log"
              domain={["dataMin", "dataMax"]}
              ticks={evalTicks(data.checkpoints[data.checkpoints.length - 1])}
              tickFormatter={(v: number) => v.toLocaleString()}
              label={{ value: "Evaluations", position: "insideBottom", offset: -8, fontSize: 12 }}
              fontSize={12}
            />
            <YAxis
              domain={[0, 1]}
              label={{ value: "Targets reached", angle: -90, position: "insideLeft", fontSize: 12 }}
              fontSize={12}
            />
            <Tooltip
              formatter={(v) => `${Math.round(Number(v) * 100)}%`}
              labelFormatter={(v) => `${Number(v).toLocaleString()} evaluations`}
            />
            <Legend verticalAlign="top" height={32} iconType="plainline" />
            {data.entries.map((e, i) => (
              <Line
                key={e.submission_id}
                dataKey={String(e.submission_id)}
                name={e.label}
                stroke={PALETTE[i % PALETTE.length]}
                strokeDasharray={e.is_baseline ? "5 4" : undefined}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-muted-foreground">
        Share of (run, target) pairs reached after a given number of evaluations, over all runs and the{" "}
        {data.targets.length} precision targets 1e2, 1e1, … 1e-8. Failed runs reach nothing. Higher and further
        left is better.
      </figcaption>
    </figure>
  );
}

/** Results paragraph written by the model from the verdicts; the numbers stay in the tables. */
function WriteUp({ query }: { query: string }) {
  const write = useMutation({ mutationFn: () => post<{ text: string }>(`/research/writeup?${query}`) });
  return (
    <section>
      <h2 className="mb-2 text-lg font-medium">Write-up</h2>
      {write.data ? (
        <div className="space-y-2 text-sm">
          {write.data.text.split(/\n+/).map((p, i) => (
            <p key={i}>{p}</p>
          ))}
          <p className="text-xs text-muted-foreground">
            AI-written from the test verdicts above. It contains no numbers by design; check it against the tables.
          </p>
        </div>
      ) : (
        <Button variant="outline" size="sm" disabled={write.isPending} onClick={() => write.mutate()}>
          {write.isPending ? "Writing…" : "Draft a results paragraph"}
        </Button>
      )}
      {write.error && <ErrorNote error={write.error} />}
    </section>
  );
}

function Results({ data }: { data: Comparison }) {
  const name = Object.fromEntries(data.entries.map((e) => [e.submission_id, e.label]));
  const query = `problem_id=${data.problem_id}&dim=${data.dim}&${data.entries
    .map((e) => `ids=${e.submission_id}`)
    .join("&")}`;
  return (
    <div className="space-y-8">
      <section>
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-medium">Summary</h2>
          <span className="flex flex-wrap gap-3">
            <Downloads path={`/research/runs?${query}`} label="All runs:" />
            <span className="text-sm text-muted-foreground">
              <a href={`/api/research/latex?${query}`} download className="text-foreground underline">
                LaTeX
              </a>
              {" · "}
              <a href={`/api/research/ioh?${query}`} download className="text-foreground underline">
                IOHanalyzer
              </a>
            </span>
          </span>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Entry</TableHead>
              <TableHead className="text-right">Score</TableHead>
              <TableHead className="text-right">Runs</TableHead>
              <TableHead className="text-right">Mean AOCC (95% CI)</TableHead>
              <TableHead className="text-right">Median AOCC</TableHead>
              <TableHead className="text-right">Mean rank</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.entries.map((e) => (
              <TableRow key={e.submission_id}>
                <TableCell>
                  <Link href={`/submissions/${e.submission_id}`} className="hover:underline">
                    {e.label}
                  </Link>
                </TableCell>
                <TableCell className="text-right tabular-nums">{fmtScore(e.score)}</TableCell>
                <TableCell className="text-right tabular-nums">{e.runs}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {e.mean.toFixed(3)} ({e.ci_low.toFixed(3)} – {e.ci_high.toFixed(3)})
                </TableCell>
                <TableCell className="text-right tabular-nums">{e.median.toFixed(3)}</TableCell>
                <TableCell className="text-right tabular-nums">{e.mean_rank?.toFixed(2) ?? "–"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className="mt-2 text-xs text-muted-foreground">
          Mean rank is taken over the {data.blocks} runs every entry shares (same instance and seed); 1 is best.
          {data.friedman_p != null &&
            ` Friedman test that all entries perform alike: p ${data.friedman_p < 0.001 ? "<" : "="} ${Math.max(data.friedman_p, 0.001).toFixed(3)}.`}
        </p>
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium">Pairwise tests</h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Pair</TableHead>
              <TableHead className="text-right">A12</TableHead>
              <TableHead className="text-right">p</TableHead>
              <TableHead className="text-right">p (Holm)</TableHead>
              <TableHead>Verdict at α = {data.alpha}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.pairs.map((p) => (
              <TableRow key={`${p.a}-${p.b}`}>
                <TableCell>
                  {name[p.a]} vs {name[p.b]}
                </TableCell>
                <TableCell className="text-right tabular-nums">{p.a12.toFixed(2)}</TableCell>
                <TableCell className="text-right tabular-nums">{fmtP(p.p)}</TableCell>
                <TableCell className="text-right tabular-nums">{fmtP(p.p_holm)}</TableCell>
                <TableCell>{p.better ? `${name[p.better]} is better` : "No significant difference"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className="mt-2 text-xs text-muted-foreground">
          Mann-Whitney U test on the AOCC of every run, two-sided, with Holm&apos;s correction for the number of
          pairs. A12 is the probability that a run of the first entry scores higher than a run of the second (0.5:
          no difference; 0.71 or more is usually called a large effect).
        </p>
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium">Runtime distribution (ECDF)</h2>
        <Ecdf data={data} />
      </section>

      <WriteUp query={query} />
    </div>
  );
}

function Research() {
  const search = useSearchParams();
  const router = useRouter();
  const problemId = search.get("problem") ?? "";
  const problems = useProblems();
  const problem = problems.data?.find((p) => p.id === problemId);
  const dim = Number(search.get("dim")) || problem?.dims[0];

  const board = useQuery({
    queryKey: ["board", problemId, dim],
    queryFn: () => api<BoardRow[]>(`/problems/${problemId}/leaderboard?dim=${dim}`),
    enabled: !!problem && !!dim,
  });
  const [picked, setPicked] = useState<number[]>();
  const chosen = picked ?? (board.data ? defaults(board.data) : []);
  const [compared, setCompared] = useState<number[]>([]);
  const comparison = useQuery({
    queryKey: ["compare", problemId, dim, compared],
    queryFn: () =>
      api<Comparison>(
        `/research/compare?problem_id=${problemId}&dim=${dim}&${compared.map((i) => `ids=${i}`).join("&")}`,
      ),
    enabled: compared.length >= 2,
  });

  const go = (p: string, d: number) => {
    setPicked(undefined);
    setCompared([]);
    router.replace(`/research?problem=${p}&dim=${d}`);
  };
  const toggle = (id: number) =>
    setPicked(chosen.includes(id) ? chosen.filter((i) => i !== id) : [...chosen, id].slice(0, MAX));

  return (
    <>
      <PageTitle title="Research">
        Compare judged optimizers on one problem with standard statistics, and download every run for your own
        analysis. All entries were run on the same instances and seeds, so their runs are directly comparable.
      </PageTitle>
      <div className="mb-6 flex flex-wrap items-center gap-2 text-sm">
        <ProblemPicker problems={problems.data ?? []} problemId={problemId} dim={dim} onChange={go} />
      </div>

      {problems.error && <ErrorNote error={problems.error} />}
      {board.isLoading && <Loading />}
      {board.error && <ErrorNote error={board.error} />}
      {board.data?.length === 0 && <Empty>No scored submissions at this dimension yet.</Empty>}
      {!!board.data?.length && (
        <section className="mb-8">
          <h2 className="mb-2 text-lg font-medium">Entries (best submission of each)</h2>
          <fieldset className="grid gap-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
            <legend className="sr-only">Entries to compare</legend>
            {board.data.map((r) => (
              <label key={r.submission_id} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={chosen.includes(r.submission_id)}
                  onChange={() => toggle(r.submission_id)}
                />
                {r.name} <span className="text-muted-foreground tabular-nums">({fmtScore(r.score)})</span>
              </label>
            ))}
          </fieldset>
          <div className="mt-3 flex items-center gap-3">
            <Button disabled={chosen.length < 2} onClick={() => setCompared(chosen)}>
              Compare {chosen.length} entries
            </Button>
            <span className="text-xs text-muted-foreground">Choose 2 to {MAX}.</span>
          </div>
        </section>
      )}
      {comparison.isLoading && <Loading />}
      {comparison.error && <ErrorNote error={comparison.error} />}
      {comparison.data && <Results data={comparison.data} />}
    </>
  );
}

export default function ResearchPage() {
  return (
    <Suspense>
      <Research />
    </Suspense>
  );
}
