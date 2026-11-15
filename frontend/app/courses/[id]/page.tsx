"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { SimilarPairs } from "@/components/similar-pairs";
import { Empty, ErrorNote, Loading } from "@/components/state";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fmtDate, fmtScore } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

export default function CourseDashboardPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, isPending } = useQuery({
    queryKey: ["dashboard", id],
    queryFn: () => api<Dashboard>(`/courses/${id}/dashboard`),
  });
  if (isPending) return <Loading />;
  if (error) return <ErrorNote error={error} />;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-muted-foreground">
          <Link href="/courses" className="hover:underline">
            Courses
          </Link>{" "}
          / instructor dashboard
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{data.course.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {data.course.students} student{data.course.students === 1 ? "" : "s"} · invite code{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">
            {data.course.invite_code}
          </code>
        </p>
      </div>
      {data.columns.length === 0 && (
        <p className="text-sm text-muted-foreground">
          This course has no contests yet.{" "}
          <Link href="/contests" className="text-foreground underline">
            Create one
          </Link>{" "}
          and choose this course.
        </p>
      )}
      {data.students.length === 0 ? (
        <Empty>No students have joined yet. Share the invite code.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Student</TableHead>
                {data.columns.map((c) => (
                  <TableHead key={c.key} className="text-right">
                    <Link href={`/contests/${c.contest_id}`} className="hover:underline">
                      {c.contest}
                    </Link>
                    <span className="block font-mono text-xs font-normal">
                      {c.problem_id}@{c.dim}
                    </span>
                  </TableHead>
                ))}
                <TableHead className="text-right">Submissions</TableHead>
                <TableHead>Last active</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.students.map((s) => (
                <TableRow key={s.user_id}>
                  <TableCell>
                    <Link href={`/profile/${s.user_id}`} className="hover:underline">
                      {s.name}
                    </Link>
                    <span className="block text-xs text-muted-foreground">{s.email}</span>
                  </TableCell>
                  {data.columns.map((c) => (
                    <TableCell key={c.key} className="text-right tabular-nums">
                      {fmtScore(s.scores[c.key])}
                    </TableCell>
                  ))}
                  <TableCell className="text-right tabular-nums">{s.submissions}</TableCell>
                  <TableCell>{s.last_active ? fmtDate(s.last_active) : "–"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        Scores are each student&apos;s best on the public instances of a contest task.
      </p>
      <p className="text-sm">
        <Link href="/tests" className="underline">
          Tests of this course
        </Link>
      </p>
      <SimilarPairs courseId={data.course.id} />
    </div>
  );
}
