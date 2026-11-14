"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

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

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-12">#</TableHead>
          <TableHead>Entry</TableHead>
          <TableHead className="text-right">Score</TableHead>
          <TableHead className="text-right">Median precision</TableHead>
          <TableHead className="text-right">IQR across seeds</TableHead>
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
            <TableCell className="text-right">
              <Link href={`/submissions/${row.submission_id}`} className="text-sm underline">
                Runs
              </Link>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
