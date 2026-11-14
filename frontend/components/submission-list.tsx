import Link from "next/link";

import { Empty } from "@/components/state";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmtDate, fmtScore } from "@/lib/format";
import type { Submission } from "@/lib/types";

type Row = Pick<Submission, "id" | "problem_id" | "dim" | "status" | "score" | "created_at"> & {
  user_name?: string;
};

export function StatusBadge({ status }: { status: string }) {
  const variant = status === "done" ? "secondary" : status === "failed" ? "destructive" : "outline";
  return <Badge variant={variant}>{status}</Badge>;
}

export function SubmissionList({
  rows,
  empty,
  showUser = false,
}: {
  rows: Row[];
  empty: string;
  showUser?: boolean;
}) {
  if (rows.length === 0) return <Empty>{empty}</Empty>;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Submitted</TableHead>
          {showUser && <TableHead>By</TableHead>}
          <TableHead>Problem</TableHead>
          <TableHead className="text-right">Dim</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Score</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((s) => (
          <TableRow key={s.id}>
            <TableCell>
              <Link href={`/submissions/${s.id}`} className="underline">
                {fmtDate(s.created_at)}
              </Link>
            </TableCell>
            {showUser && <TableCell>{s.user_name}</TableCell>}
            <TableCell>
              <Link href={`/problems/${s.problem_id}`} className="font-mono hover:underline">
                {s.problem_id}
              </Link>
            </TableCell>
            <TableCell className="text-right tabular-nums">{s.dim}</TableCell>
            <TableCell>
              <StatusBadge status={s.status} />
            </TableCell>
            <TableCell className="text-right font-medium tabular-nums">
              {fmtScore(s.score)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
