"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Downloads } from "@/components/downloads";
import { Empty, ErrorNote, Loading } from "@/components/state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, post } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { fmtDate, fmtScore } from "@/lib/format";
import type { Contest, ContestBoardRow } from "@/lib/types";

export default function ContestPage() {
  const { id } = useParams<{ id: string }>();
  const me = useMe();
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const contest = useQuery({
    queryKey: ["contest", id],
    queryFn: () => api<Contest>(`/contests/${id}`),
    refetchInterval: (q) => (q.state.data?.phase === "finalising" ? 3000 : false),
  });
  const board = useQuery({
    queryKey: ["contest-board", id, contest.data?.phase],
    queryFn: () => api<ContestBoardRow[]>(`/contests/${id}/leaderboard`),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["contest", id] });
  const join = useMutation({ mutationFn: () => post(`/contests/${id}/join`, { code }), onSuccess: refresh });
  const finalise = useMutation({ mutationFn: () => post(`/contests/${id}/finalise`), onSuccess: refresh });

  if (contest.isPending) return <Loading />;
  if (contest.error) return <ErrorNote error={contest.error} />;
  const c = contest.data;
  const keys = c.tasks.map((t) => `${t.problem_id}@${t.dim}`);
  const open = c.phase === "upcoming" || c.phase === "running";

  return (
    <div className="space-y-8">
      <div>
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link href="/contests" className="hover:underline">
            Contests
          </Link>
          <Badge variant={c.phase === "running" ? "default" : "secondary"}>{c.phase}</Badge>
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{c.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {fmtDate(c.starts_at)} to {fmtDate(c.ends_at)} · {c.participants} participant
          {c.participants === 1 ? "" : "s"}
        </p>
        {c.description && <p className="mt-3 max-w-3xl whitespace-pre-line text-sm">{c.description}</p>}
      </div>

      {c.can_manage && (
        <section className="space-y-2 rounded-xl border p-4 text-sm">
          <h2 className="font-medium">Organiser</h2>
          {c.invite_code && (
            <p>
              Invite code: <code className="rounded bg-muted px-1.5 py-0.5 font-mono">{c.invite_code}</code>
            </p>
          )}
          {c.phase !== "final" && c.phase !== "finalising" && (
            <>
              <p className="text-muted-foreground">
                Finalising closes the contest now and re-runs every participant&apos;s best
                submission per task on held-out instances. It cannot be undone.
              </p>
              <Button
                variant="destructive"
                size="sm"
                disabled={finalise.isPending}
                onClick={() => {
                  if (window.confirm("Close this contest and compute the final ranking?")) finalise.mutate();
                }}
              >
                Close and finalise
              </Button>
            </>
          )}
          {finalise.error && <ErrorNote error={finalise.error} />}
        </section>
      )}

      {c.phase === "finalising" && (
        <p role="status" className="rounded-lg border p-4 text-sm">
          Final evaluation on held-out instances is running. This page updates by itself.
        </p>
      )}

      {me && !c.joined && open && (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            join.mutate();
          }}
        >
          {c.invite_only && !c.course_id && (
            <Input
              aria-label="Invite code"
              placeholder="Invite code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-48"
              required
            />
          )}
          <Button type="submit" disabled={join.isPending}>
            Join contest
          </Button>
          {join.error && <ErrorNote error={join.error} />}
        </form>
      )}
      {!me && open && (
        <p className="text-sm">
          <Link href="/login" className="underline">
            Sign in
          </Link>{" "}
          to join.
        </p>
      )}

      <section>
        <h2 className="mb-2 text-lg font-medium">Tasks</h2>
        <ul className="space-y-1 text-sm">
          {c.tasks.map((t) => (
            <li key={`${t.problem_id}@${t.dim}`}>
              <Link
                href={`/problems/${t.problem_id}?contest=${c.id}&dim=${t.dim}`}
                className="underline"
              >
                <span className="font-mono">{t.problem_id}</span> at dimension {t.dim}
              </Link>
            </li>
          ))}
        </ul>
        {c.joined && c.phase === "running" && (
          <p className="mt-2 text-sm text-muted-foreground">
            Open a task from here to submit to this contest.
          </p>
        )}
      </section>

      <section>
        <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-medium">
            {c.phase === "final" ? "Final ranking" : "Public leaderboard"}
          </h2>
          {!!board.data?.length && <Downloads path={`/contests/${c.id}/leaderboard/export`} />}
        </div>
        <p className="mb-3 text-sm text-muted-foreground">
          {c.phase === "final"
            ? "Scores of each participant's best submission per task, re-run on held-out instances."
            : "Best score per task on the public instances. The final ranking can differ."}
        </p>
        {board.isPending && <Loading />}
        {board.error && <ErrorNote error={board.error} />}
        {board.data?.length === 0 && <Empty>No scored submissions yet.</Empty>}
        {!!board.data?.length && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">#</TableHead>
                <TableHead>Participant</TableHead>
                {keys.map((k) => (
                  <TableHead key={k} className="text-right font-mono">
                    {k}
                  </TableHead>
                ))}
                <TableHead className="text-right">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {board.data.map((row) => (
                <TableRow key={row.user_id}>
                  <TableCell className="tabular-nums">{row.rank}</TableCell>
                  <TableCell>
                    <Link href={`/profile/${row.user_id}`} className="hover:underline">
                      {row.name}
                    </Link>
                  </TableCell>
                  {keys.map((k) => (
                    <TableCell key={k} className="text-right tabular-nums">
                      {fmtScore(row.scores[k])}
                    </TableCell>
                  ))}
                  <TableCell className="text-right font-medium tabular-nums">
                    {fmtScore(row.total)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
    </div>
  );
}
