"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Empty, ErrorNote, Loading } from "@/components/state";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, post } from "@/lib/api";
import type { Problem, SimilarPair } from "@/lib/types";

type Opinion = { verdict: string; reasons: string };
const selectClass = "h-8 rounded-lg border bg-background px-2 text-sm";

function OpinionCell({ courseId, pair }: { courseId: number; pair: SimilarPair }) {
  const ask = useMutation({ mutationFn: () => post<Opinion>(`/courses/${courseId}/similarity/opinion`, { a: pair.a, b: pair.b }) });
  if (ask.data)
    return (
      <span className="text-sm">
        <strong>{ask.data.verdict}</strong> (AI-assisted): {ask.data.reasons}
      </span>
    );
  return (
    <>
      <Button variant="outline" size="sm" disabled={ask.isPending} onClick={() => ask.mutate()}>
        {ask.isPending ? "Asking…" : "Second opinion"}
      </Button>
      {ask.error && <ErrorNote error={ask.error} />}
    </>
  );
}

/** Instructor-only: pairs of students' latest submissions with similar code. */
export function SimilarPairs({ courseId }: { courseId: number }) {
  const problems = useQuery({ queryKey: ["problems"], queryFn: () => api<Problem[]>("/problems") });
  const [problemId, setProblemId] = useState("");
  const [dim, setDim] = useState(0);
  const problem = problems.data?.find((p) => p.id === problemId);
  const pairs = useQuery({
    queryKey: ["similarity", courseId, problemId, dim],
    queryFn: () => api<SimilarPair[]>(`/courses/${courseId}/similarity?problem_id=${problemId}&dim=${dim}`),
    enabled: !!problemId && !!dim,
  });

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-medium">Similar code</h2>
      <p className="max-w-3xl text-sm text-muted-foreground">
        Compares each student&apos;s latest judged submission on a problem by tokens and syntax tree, with names and
        numbers ignored. Pairs explained by the same starter template are left out. A high score is a reason to talk to
        the students, not proof of copying, and this does not detect AI-written code.
      </p>
      <div className="flex flex-wrap gap-2">
        <select
          aria-label="Problem"
          className={selectClass}
          value={problemId}
          onChange={(e) => {
            setProblemId(e.target.value);
            setDim(problems.data?.find((p) => p.id === e.target.value)?.dims[0] ?? 0);
          }}
        >
          <option value="">Choose a problem</option>
          {problems.data?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.id} {p.name}
            </option>
          ))}
        </select>
        {problem && (
          <select aria-label="Dimension" className={selectClass} value={dim} onChange={(e) => setDim(Number(e.target.value))}>
            {problem.dims.map((d) => (
              <option key={d} value={d}>
                dimension {d}
              </option>
            ))}
          </select>
        )}
      </div>
      {pairs.isFetching ? (
        <Loading rows={2} />
      ) : pairs.error ? (
        <ErrorNote error={pairs.error} />
      ) : pairs.data && pairs.data.length === 0 ? (
        <Empty>No pairs to review.</Empty>
      ) : pairs.data ? (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Students</TableHead>
                <TableHead className="text-right">Tokens</TableHead>
                <TableHead className="text-right">Structure</TableHead>
                <TableHead>Second opinion</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pairs.data.map((p) => (
                <TableRow key={`${p.a}-${p.b}`}>
                  <TableCell>
                    <Link href={`/submissions/${p.a}`} className="underline">
                      {p.a_name}
                    </Link>{" "}
                    and{" "}
                    <Link href={`/submissions/${p.b}`} className="underline">
                      {p.b_name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{Math.round(p.token * 100)}%</TableCell>
                  <TableCell className="text-right tabular-nums">{Math.round(p.structure * 100)}%</TableCell>
                  <TableCell className="whitespace-normal">
                    <OpinionCell courseId={courseId} pair={p} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
    </section>
  );
}
