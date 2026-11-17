"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Downloads } from "@/components/downloads";
import { Empty, ErrorNote, Loading } from "@/components/state";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fmtPrecision, fmtScore } from "@/lib/format";
import type { BoardRow } from "@/lib/types";

/** Per-problem leaderboard: each user's best submission, baselines flagged. */
export function BoardTable({ problemId, dim }: { problemId: string; dim: number }) {
  const { data, error, isPending } = useQuery({
    queryKey: ["board", problemId, dim],
    queryFn: () => api<BoardRow[]>(`/problems/${problemId}/leaderboard?dim=${dim}`),
  });
  if (isPending) return <Loading />;
  if (error) return <ErrorNote error={error} />;
  if (data.length === 0) return <Empty>No scored submissions at this dimension yet.</Empty>;
  const ai = data.find((r) => r.is_baseline && r.name.startsWith("AI-written"));
  const vsAi = (score: number) => {
    if (!ai || ai.score <= 0) return "–";
    const pct = Math.round((score / ai.score - 1) * 100);
    return `${pct > 0 ? "+" : ""}${pct}%`;
  };

  return (
    <>
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <Link href={`/research?problem=${problemId}&dim=${dim}`} className="text-sm underline">
          Compare entries statistically
        </Link>
        <Downloads path={`/problems/${problemId}/leaderboard/export?dim=${dim}`} />
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">#</TableHead>
            <TableHead>Entry</TableHead>
            <TableHead className="text-right">Score</TableHead>
            <TableHead className="text-right">Median precision</TableHead>
            <TableHead className="text-right">IQR across seeds</TableHead>
            {ai && <TableHead className="text-right">vs AI baseline</TableHead>}
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((row) => (
            <TableRow key={row.user_id}>
              <TableCell className="tabular-nums">{row.rank}</TableCell>
              <TableCell>
                {row.is_baseline ? (
                  <span className="flex items-center gap-2">
                    {row.name.replace(" (baseline)", "")} <Badge variant="outline">baseline</Badge>
                  </span>
                ) : (
                  <Link href={`/profile/${row.user_id}`} className="hover:underline">
                    {row.name}
                  </Link>
                )}
                {row.institution && (
                  <span className="block text-xs text-muted-foreground">{row.institution}</span>
                )}
              </TableCell>
              <TableCell className="text-right font-medium tabular-nums">
                {fmtScore(row.score)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {fmtPrecision(row.median_precision)}
              </TableCell>
              <TableCell className="text-right tabular-nums">{row.iqr?.toFixed(3) ?? "–"}</TableCell>
              {ai && <TableCell className="text-right tabular-nums">{vsAi(row.score)}</TableCell>}
              <TableCell className="text-right">
                <Link href={`/submissions/${row.submission_id}`} className="text-sm underline">
                  Runs
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
}
