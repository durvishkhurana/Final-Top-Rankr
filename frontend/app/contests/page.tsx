"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useProblems } from "@/components/problem-picker";
import { Empty, ErrorNote, Loading, PageTitle } from "@/components/state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, post } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import type { Contest, Course } from "@/lib/types";

const local = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);

function CreateContest({ onDone }: { onDone: () => void }) {
  const router = useRouter();
  const problems = useProblems();
  const courses = useQuery({ queryKey: ["courses"], queryFn: () => api<Course[]>("/courses") });
  const [tasks, setTasks] = useState<string[]>([]); // "problem@dim"
  const create = useMutation({
    mutationFn: (form: FormData) =>
      post<Contest>("/contests", {
        title: form.get("title"),
        description: form.get("description"),
        starts_at: new Date(String(form.get("starts_at"))).toISOString(),
        ends_at: new Date(String(form.get("ends_at"))).toISOString(),
        invite_only: form.get("invite_only") === "on",
        course_id: form.get("course_id") ? Number(form.get("course_id")) : null,
        hint_level: form.get("hint_level"),
        tasks: tasks.map((t) => ({ problem_id: t.split("@")[0], dim: Number(t.split("@")[1]) })),
      }),
    onSuccess: (c) => router.push(`/contests/${c.id}`),
  });
  const now = new Date();

  return (
    <form
      className="mb-8 max-w-2xl space-y-4 rounded-xl border p-4"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate(new FormData(e.currentTarget));
      }}
    >
      <div className="space-y-1.5">
        <Label htmlFor="title">Title</Label>
        <Input id="title" name="title" required maxLength={150} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="description">Description</Label>
        <Textarea id="description" name="description" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="starts_at">Starts</Label>
          <Input id="starts_at" name="starts_at" type="datetime-local" required defaultValue={local(now)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ends_at">Ends</Label>
          <Input id="ends_at" name="ends_at" type="datetime-local" required
            defaultValue={local(new Date(now.getTime() + 7 * 86400000))} />
        </div>
      </div>
      <fieldset>
        <legend className="mb-1.5 text-sm font-medium">Tasks ({tasks.length} selected)</legend>
        <div className="max-h-56 space-y-1 overflow-y-auto rounded-lg border p-2 text-sm">
          {problems.data?.map((p) => (
            <div key={p.id} className="flex flex-wrap items-center gap-x-3">
              <span className="w-56 truncate">
                <span className="font-mono">{p.id}</span> {p.name}
              </span>
              {p.dims.map((d) => {
                const key = `${p.id}@${d}`;
                return (
                  <label key={key} className="flex items-center gap-1">
                    <input
                      type="checkbox"
                      checked={tasks.includes(key)}
                      onChange={(e) =>
                        setTasks(e.target.checked ? [...tasks, key] : tasks.filter((t) => t !== key))
                      }
                    />
                    dim {d}
                  </label>
                );
              })}
            </div>
          ))}
        </div>
      </fieldset>
      <div className="flex flex-wrap items-center gap-6 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" name="invite_only" /> Invite code required
        </label>
        <label className="flex items-center gap-2">
          AI coach
          <select name="hint_level" defaultValue="specific" className="h-8 rounded-lg border bg-background px-2">
            <option value="specific">specific hints</option>
            <option value="concept">concepts only</option>
            <option value="off">off</option>
          </select>
        </label>
        {!!courses.data?.filter((c) => c.teaches).length && (
          <label className="flex items-center gap-2">
            For course
            <select name="course_id" className="h-8 rounded-lg border bg-background px-2">
              <option value="">none (public)</option>
              {courses.data.filter((c) => c.teaches).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {create.error && <ErrorNote error={create.error} />}
      <div className="flex gap-2">
        <Button type="submit" disabled={create.isPending || tasks.length === 0}>
          Create contest
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export default function ContestsPage() {
  const me = useMe();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const { data, error, isPending } = useQuery({
    queryKey: ["contests"],
    queryFn: () => api<Contest[]>("/contests"),
  });
  const staff = me?.role === "instructor" || me?.role === "admin";

  return (
    <>
      <PageTitle title="Contests">
        During a contest you see scores on public instances. When it closes, each
        participant&apos;s best submission per task is re-run on instances nobody has seen, and
        those scores decide the final ranking.
      </PageTitle>
      {staff && !creating && (
        <Button className="mb-6" onClick={() => setCreating(true)}>
          New contest
        </Button>
      )}
      {creating && (
        <CreateContest
          onDone={() => {
            setCreating(false);
            queryClient.invalidateQueries({ queryKey: ["contests"] });
          }}
        />
      )}
      {isPending && <Loading />}
      {error && <ErrorNote error={error} />}
      {data?.length === 0 && <Empty>No contests yet.</Empty>}
      <div className="grid gap-4 sm:grid-cols-2">
        {data?.map((c) => (
          <Link key={c.id} href={`/contests/${c.id}`} className="group">
            <Card className="h-full transition-colors group-hover:border-foreground/40">
              <CardHeader>
                <CardDescription className="flex items-center gap-2">
                  <Badge variant={c.phase === "running" ? "default" : "secondary"}>{c.phase}</Badge>
                  {c.invite_only && <Badge variant="outline">invite only</Badge>}
                  {c.course_id && <Badge variant="outline">course</Badge>}
                </CardDescription>
                <CardTitle>{c.title}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {c.tasks.length} task{c.tasks.length === 1 ? "" : "s"} · {c.participants}{" "}
                participant{c.participants === 1 ? "" : "s"} · ends {fmtDate(c.ends_at)}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}
