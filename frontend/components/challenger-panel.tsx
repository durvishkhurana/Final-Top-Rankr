"use client";

import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { fmtDate, fmtScore } from "@/lib/format";
import type { Challenger, ChallengerDetail } from "@/lib/types";

/** History of the evolving AI challenger on one problem and dimension, if it has one. */
export function ChallengerPanel({ problemId, dim }: { problemId: string; dim: number }) {
  const list = useQuery({
    queryKey: ["challengers", problemId, dim],
    queryFn: () => api<Challenger[]>(`/challengers?problem_id=${problemId}&dim=${dim}`),
  });
  const id = list.data?.[0]?.id;
  const detail = useQuery({
    queryKey: ["challenger", id],
    queryFn: () => api<ChallengerDetail>(`/challengers/${id}`),
    enabled: id !== undefined,
    refetchInterval: (q) => (q.state.data?.running ? 5000 : false),
  });
  const c = detail.data;
  if (!c) return null;

  // best score so far after each judged generation
  const curve = c.history.map((g, i) => ({
    number: g.number,
    score: g.score,
    best: Math.max(...c.history.slice(0, i + 1).map((h) => h.score ?? 0)),
  }));

  return (
    <section className="mt-8 space-y-3">
      <h2 className="text-lg font-medium">AI challenger</h2>
      <p className="max-w-3xl text-sm text-muted-foreground">
        An optimizer written by a language model that improves itself one generation at a time. Each generation
        starts from the best one so far and sees only the public description and the judge&apos;s summary of how it
        did, never the function. Its best generation is its entry on the leaderboard above.
        {c.running && " A new generation is being written and judged now."}
      </p>
      {c.history.length > 1 && (
        <figure className="h-48 w-full max-w-2xl">
          <ResponsiveContainer>
            <LineChart data={curve} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="number" fontSize={12} allowDecimals={false} />
              <YAxis domain={[0, 1000]} fontSize={12} width={40} />
              <Tooltip labelFormatter={(n) => `Generation ${n}`} formatter={(v) => fmtScore(Number(v))} />
              <Line dataKey="best" name="Best so far" stroke="var(--foreground)" dot={false} isAnimationActive={false} />
              <Line
                dataKey="score"
                name="This generation"
                stroke="#0072B2"
                strokeDasharray="4 3"
                connectNulls={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </figure>
      )}
      <ol className="space-y-2 text-sm">
        {[...c.history].reverse().map((g) => (
          <li key={g.number} className="rounded-lg border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">Generation {g.number}</span>
              {g.is_champion && <Badge>champion</Badge>}
              {g.status !== "done" && <Badge variant="outline">{g.status}</Badge>}
              <span className="tabular-nums">{g.score != null && `score ${fmtScore(g.score)}`}</span>
              <span className="ml-auto text-xs text-muted-foreground">{fmtDate(g.created_at)}</span>
            </div>
            {g.approach && <p className="mt-1">{g.approach}</p>}
            {g.changes && <p className="mt-1 text-muted-foreground">{g.changes}</p>}
            {g.status === "failed" && g.error && <p className="mt-1 text-destructive">{g.error}</p>}
          </li>
        ))}
      </ol>
    </section>
  );
}
