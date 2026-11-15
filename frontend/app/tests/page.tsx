"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Empty, ErrorNote, Loading, PageTitle } from "@/components/state";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, post } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import type { Course, Exam } from "@/lib/types";

const local = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);

function CreateForm({ courses, onDone }: { courses: Course[]; onDone: () => void }) {
  const create = useMutation({
    mutationFn: (form: FormData) =>
      post<Exam>("/tests", {
        course_id: Number(form.get("course_id")),
        title: form.get("title"),
        description: form.get("description"),
        starts_at: new Date(String(form.get("starts_at"))).toISOString(),
        ends_at: new Date(String(form.get("ends_at"))).toISOString(),
        camera_checks: form.get("camera_checks") === "on",
      }),
    onSuccess: onDone,
  });
  const now = new Date();
  return (
    <form
      className="space-y-3 rounded-xl border p-4"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate(new FormData(e.currentTarget));
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="course_id">Course</Label>
          <select id="course_id" name="course_id" className="h-8 w-full rounded-lg border bg-background px-2 text-sm">
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="title">Title</Label>
          <Input id="title" name="title" required maxLength={150} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="starts_at">Opens</Label>
          <Input id="starts_at" name="starts_at" type="datetime-local" required defaultValue={local(now)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="ends_at">Closes</Label>
          <Input
            id="ends_at"
            name="ends_at"
            type="datetime-local"
            required
            defaultValue={local(new Date(now.getTime() + 7 * 86_400_000))}
          />
        </div>
      </div>
      <div className="space-y-1">
        <Label htmlFor="description">Instructions</Label>
        <Textarea id="description" name="description" rows={2} maxLength={5000} />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" name="camera_checks" defaultChecked /> Offer camera checks (students can still
        decline)
      </label>
      {create.error && <ErrorNote error={create.error} />}
      <Button type="submit" disabled={create.isPending}>
        Create draft
      </Button>
    </form>
  );
}

export default function TestsPage() {
  const me = useMe();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const tests = useQuery({ queryKey: ["tests"], queryFn: () => api<Exam[]>("/tests"), enabled: !!me });
  const courses = useQuery({ queryKey: ["courses"], queryFn: () => api<Course[]>("/courses"), enabled: !!me });
  const teaching = courses.data?.filter((c) => c.teaches) ?? [];

  if (me === undefined) return <Loading />;
  if (!me) return <ErrorNote error={new Error("Log in to see the tests of your courses.")} />;
  return (
    <div className="space-y-6">
      <PageTitle title="Tests">
        Tests of your courses. Some questions are personalised from your own submissions; the answers to
        numeric questions are computed by the platform.
      </PageTitle>
      {teaching.length > 0 &&
        (creating ? (
          <CreateForm
            courses={teaching}
            onDone={() => {
              setCreating(false);
              queryClient.invalidateQueries({ queryKey: ["tests"] });
            }}
          />
        ) : (
          <Button onClick={() => setCreating(true)}>New test</Button>
        ))}
      {tests.isPending ? (
        <Loading />
      ) : tests.error ? (
        <ErrorNote error={tests.error} />
      ) : tests.data.length === 0 ? (
        <Empty>No tests yet.</Empty>
      ) : (
        <ul className="space-y-3">
          {tests.data.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-3 rounded-xl border p-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{t.title}</span>
                  <Badge variant="outline">{t.status}</Badge>
                  {t.attempt && <Badge variant="secondary">{t.attempt.status.replace("_", " ")}</Badge>}
                </div>
                <p className="text-sm text-muted-foreground">
                  {t.course_title} · {fmtDate(t.starts_at)} to {fmtDate(t.ends_at)} · {t.questions} question
                  {t.questions === 1 ? "" : "s"}
                  {t.attempt?.total != null && ` · your score ${t.attempt.total} / ${t.max_total}`}
                </p>
              </div>
              {t.teaches ? (
                <div className="flex gap-2">
                  <Link href={`/tests/${t.id}/edit`} className={buttonVariants({ variant: "outline", size: "sm" })}>
                    Edit
                  </Link>
                  <Link href={`/tests/${t.id}/results`} className={buttonVariants({ variant: "outline", size: "sm" })}>
                    Results
                  </Link>
                </div>
              ) : (
                <Link href={`/tests/${t.id}`} className={buttonVariants({ size: "sm" })}>
                  {t.attempt ? "Open" : "Take"}
                </Link>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
