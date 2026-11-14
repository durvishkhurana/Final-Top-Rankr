"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Empty, ErrorNote, Loading, PageTitle } from "@/components/state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, post } from "@/lib/api";
import { useMe } from "@/lib/auth";
import type { Course } from "@/lib/types";

export default function CoursesPage() {
  const me = useMe();
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const courses = useQuery({
    queryKey: ["courses"],
    queryFn: () => api<Course[]>("/courses"),
    enabled: !!me,
  });
  const done = () => {
    setCode("");
    setTitle("");
    queryClient.invalidateQueries({ queryKey: ["courses"] });
    queryClient.invalidateQueries({ queryKey: ["contests"] });
  };
  const join = useMutation({ mutationFn: () => post("/courses/join", { code }), onSuccess: done });
  const create = useMutation({ mutationFn: () => post("/courses", { title }), onSuccess: done });

  if (me === undefined) return <Loading />;
  if (me === null) {
    return (
      <p className="text-sm">
        <Link href="/login" className="underline">
          Sign in
        </Link>{" "}
        to see your courses.
      </p>
    );
  }
  const staff = me.role !== "student";

  return (
    <>
      <PageTitle title="Courses">
        A course groups students under an instructor. Its contests are visible only to its
        members, and the instructor sees everyone&apos;s progress.
      </PageTitle>
      <div className="mb-8 flex flex-wrap gap-6">
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            join.mutate();
          }}
        >
          <Input aria-label="Course invite code" placeholder="Invite code" value={code}
            onChange={(e) => setCode(e.target.value)} className="w-44" required />
          <Button type="submit" variant="outline" disabled={join.isPending}>
            Join course
          </Button>
        </form>
        {staff && (
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <Input aria-label="New course title" placeholder="New course title" value={title}
              onChange={(e) => setTitle(e.target.value)} className="w-64" required />
            <Button type="submit" disabled={create.isPending}>
              Create course
            </Button>
          </form>
        )}
      </div>
      {(join.error || create.error) && <ErrorNote error={join.error ?? create.error} />}
      {courses.isPending && <Loading />}
      {courses.error && <ErrorNote error={courses.error} />}
      {courses.data?.length === 0 && <Empty>You are not in any course yet.</Empty>}
      <div className="grid gap-4 sm:grid-cols-2">
        {courses.data?.map((c) => (
          <Card key={c.id}>
            <CardHeader>
              <CardDescription>
                {c.teaches ? "You teach this course" : `Instructor: ${c.instructor}`}
              </CardDescription>
              <CardTitle>{c.title}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                {c.students} student{c.students === 1 ? "" : "s"}
              </p>
              {c.teaches && (
                <p>
                  Invite code:{" "}
                  <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">
                    {c.invite_code}
                  </code>{" "}
                  ·{" "}
                  <Link href={`/courses/${c.id}`} className="text-foreground underline">
                    Dashboard
                  </Link>
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
