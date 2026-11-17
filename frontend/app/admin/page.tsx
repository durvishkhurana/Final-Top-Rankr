"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { ErrorNote, Loading, PageTitle } from "@/components/state";
import { SubmissionList } from "@/components/submission-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, patch, post } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { CodeEditor } from "@/components/code-editor";
import { STATUS_TEXT, SmokeChecks } from "@/components/smoke-checks";
import { fmtScore } from "@/lib/format";
import type { AdminUser, Challenger, Contribution, Problem, Role, Submission } from "@/lib/types";

const selectClass = "h-8 rounded-lg border bg-background px-2 text-sm";

function Users({ myId }: { myId: number }) {
  const queryClient = useQueryClient();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => api<AdminUser[]>("/admin/users") });
  const setRole = useMutation({
    mutationFn: ({ id, role }: { id: number; role: Role }) => patch(`/admin/users/${id}`, { role }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });
  if (users.isPending) return <Loading />;
  if (users.error) return <ErrorNote error={users.error} />;
  return (
    <>
      {setRole.error && <ErrorNote error={setRole.error} />}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Role</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.data.map((u) => (
            <TableRow key={u.id}>
              <TableCell className="space-x-2">
                <span>{u.name}</span>
                {u.is_bot && <Badge variant="outline">baseline</Badge>}
                {u.is_demo && <Badge variant="outline">demo</Badge>}
              </TableCell>
              <TableCell>{u.is_bot ? "–" : u.email}</TableCell>
              <TableCell>
                {u.is_bot || u.id === myId ? (
                  u.role
                ) : (
                  <select
                    aria-label={`Role of ${u.name}`}
                    className={selectClass}
                    value={u.role}
                    onChange={(e) => setRole.mutate({ id: u.id, role: e.target.value as Role })}
                  >
                    <option>student</option>
                    <option>instructor</option>
                    <option>admin</option>
                  </select>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
}

function Problems() {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const problems = useQuery({
    queryKey: ["admin-problems"],
    queryFn: () => api<Problem[]>("/admin/problems"),
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-problems"] });
    queryClient.invalidateQueries({ queryKey: ["problems"] });
  };
  const setActive = useMutation({
    mutationFn: (p: Problem) => patch(`/admin/problems/${p.id}`, { is_active: !p.is_active }),
    onSettled: refresh,
  });
  const baselines = useMutation({
    mutationFn: ({ id, dim }: { id: string; dim: number }) =>
      post(`/admin/problems/${id}/baselines`, { dim }),
    onSuccess: (_, { id, dim }) => setNote(`Queued the three baselines on ${id} at dimension ${dim}.`),
  });
  const aiBaseline = useMutation({
    mutationFn: ({ id, dim }: { id: string; dim: number }) =>
      post(`/admin/problems/${id}/ai-baseline`, { dim }),
    onSuccess: (_, { id, dim }) => setNote(`Queued an AI-written optimizer on ${id} at dimension ${dim}.`),
  });
  if (problems.isPending) return <Loading />;
  if (problems.error) return <ErrorNote error={problems.error} />;
  return (
    <>
      {note && (
        <p role="status" className="mb-3 rounded-lg border p-3 text-sm">
          {note}
        </p>
      )}
      {(setActive.error || baselines.error || aiBaseline.error) && (
        <ErrorNote error={setActive.error ?? baselines.error ?? aiBaseline.error} />
      )}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Problem</TableHead>
            <TableHead>Visible</TableHead>
            <TableHead>Run baselines at dimension</TableHead>
            <TableHead>AI baseline at dimension</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {problems.data.map((p) => (
            <TableRow key={p.id}>
              <TableCell>
                <span className="font-mono">{p.id}</span> {p.name}
              </TableCell>
              <TableCell>
                <Button variant="outline" size="sm" onClick={() => setActive.mutate(p)}>
                  {p.is_active ? "Hide" : "Show"}
                </Button>
              </TableCell>
              <TableCell className="space-x-2">
                {p.dims.map((dim) => (
                  <Button
                    key={dim}
                    variant="outline"
                    size="sm"
                    disabled={baselines.isPending}
                    onClick={() => baselines.mutate({ id: p.id, dim })}
                  >
                    {dim}
                  </Button>
                ))}
              </TableCell>
              <TableCell className="space-x-2">
                {p.dims.map((dim) => (
                  <Button
                    key={dim}
                    variant="outline"
                    size="sm"
                    disabled={aiBaseline.isPending}
                    onClick={() => aiBaseline.mutate({ id: p.id, dim })}
                  >
                    {dim}
                  </Button>
                ))}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
}

function Contributions() {
  const queryClient = useQueryClient();
  const items = useQuery({
    queryKey: ["admin-contributions"],
    queryFn: () => api<Contribution[]>("/admin/contributions"),
  });
  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: "approve" | "reject" }) =>
      post(`/admin/contributions/${id}/${decision}`),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-contributions"] });
      queryClient.invalidateQueries({ queryKey: ["admin-problems"] });
    },
  });
  if (items.isPending) return <Loading />;
  if (items.error) return <ErrorNote error={items.error} />;
  if (items.data.length === 0) return <p className="text-sm text-muted-foreground">No contributions yet.</p>;
  return (
    <div className="space-y-4">
      {decide.error && <ErrorNote error={decide.error} />}
      {items.data.map((c) => (
        <details key={c.id} className="rounded-lg border p-3" open={c.status === "pending"}>
          <summary className="cursor-pointer">
            <span className="font-medium">{c.name}</span>{" "}
            <Badge variant="outline">{STATUS_TEXT[c.status] ?? c.status}</Badge>{" "}
            {c.ai_built && <Badge variant="outline">AI-drafted</Badge>}
          </summary>
          <div className="mt-3 space-y-3 text-sm">
            <p>{c.summary}</p>
            {c.description && <p className="text-muted-foreground">{c.description}</p>}
            <p>
              Box {c.lower} to {c.upper}, dimensions {c.dims.join(", ")}, {c.level}
            </p>
            <CodeEditor value={c.source} readOnly height={200} />
            <SmokeChecks item={c} />
            {c.status === "pending" && (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: c.id, decision: "approve" })}
                >
                  Approve
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: c.id, decision: "reject" })}
                >
                  Reject
                </Button>
              </div>
            )}
          </div>
        </details>
      ))}
    </div>
  );
}

function Challengers() {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: ["challengers"], queryFn: () => api<Challenger[]>("/challengers") });
  const problems = useQuery({ queryKey: ["admin-problems"], queryFn: () => api<Problem[]>("/admin/problems") });
  const [problemId, setProblemId] = useState("");
  const problem = problems.data?.find((p) => p.id === problemId);
  const [dim, setDim] = useState<number>();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["challengers"] });
  const start = useMutation({
    mutationFn: () => post("/challengers", { problem_id: problemId, dim: dim ?? problem?.dims[0] }),
    onSettled: refresh,
  });
  const evolve = useMutation({ mutationFn: (id: number) => post(`/challengers/${id}/evolve`), onSettled: refresh });
  const toggle = useMutation({
    mutationFn: (c: Challenger) => patch(`/challengers/${c.id}`, { is_active: !c.active }),
    onSettled: refresh,
  });
  if (list.isPending) return <Loading />;
  if (list.error) return <ErrorNote error={list.error} />;
  const error = start.error ?? evolve.error ?? toggle.error;
  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-sm text-muted-foreground">
        A challenger writes a new generation of its optimizer, judges it and keeps the best. Active challengers evolve
        once a day; each generation is one AI request and counts against the daily limits.
      </p>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="ch-problem">Start a challenger on</label>
        <select
          id="ch-problem"
          className={selectClass}
          value={problemId}
          onChange={(e) => {
            setProblemId(e.target.value);
            setDim(undefined);
          }}
        >
          <option value="" disabled>
            problem…
          </option>
          {problems.data?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.id} {p.name}
            </option>
          ))}
        </select>
        {problem && (
          <select
            aria-label="Dimension"
            className={selectClass}
            value={dim ?? problem.dims[0]}
            onChange={(e) => setDim(Number(e.target.value))}
          >
            {problem.dims.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        )}
        <Button size="sm" disabled={!problem || start.isPending} onClick={() => start.mutate()}>
          Start
        </Button>
      </div>
      {error && <ErrorNote error={error} />}
      {list.data.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Problem</TableHead>
              <TableHead className="text-right">Generations</TableHead>
              <TableHead className="text-right">Best score</TableHead>
              <TableHead>Daily</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.data.map((c) => (
              <TableRow key={c.id}>
                <TableCell>
                  <Link href={`/problems/${c.problem_id}?dim=${c.dim}`} className="hover:underline">
                    <span className="font-mono">{c.problem_id}</span> at dimension {c.dim}
                  </Link>
                </TableCell>
                <TableCell className="text-right tabular-nums">{c.generations}</TableCell>
                <TableCell className="text-right tabular-nums">{fmtScore(c.best_score)}</TableCell>
                <TableCell>
                  <Button variant="outline" size="sm" onClick={() => toggle.mutate(c)}>
                    {c.active ? "Pause" : "Resume"}
                  </Button>
                </TableCell>
                <TableCell className="text-right">
                  <Button size="sm" disabled={c.running || evolve.isPending} onClick={() => evolve.mutate(c.id)}>
                    {c.running ? "Running…" : "Evolve now"}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function Recent() {
  const subs = useQuery({
    queryKey: ["admin-submissions"],
    queryFn: () => api<Submission[]>("/admin/submissions"),
  });
  if (subs.isPending) return <Loading />;
  if (subs.error) return <ErrorNote error={subs.error} />;
  return <SubmissionList rows={subs.data} showUser empty="No submissions yet." />;
}

export default function AdminPage() {
  const me = useMe();
  if (me === undefined) return <Loading />;
  if (me?.role !== "admin") return <ErrorNote error={new Error("This page is for admins.")} />;
  return (
    <>
      <PageTitle title="Admin" />
      <Tabs defaultValue="users">
        <TabsList>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="problems">Problems</TabsTrigger>
          <TabsTrigger value="contributions">Contributions</TabsTrigger>
          <TabsTrigger value="challengers">AI challengers</TabsTrigger>
          <TabsTrigger value="submissions">Recent submissions</TabsTrigger>
        </TabsList>
        <TabsContent value="users" className="pt-3">
          <Users myId={me.id} />
        </TabsContent>
        <TabsContent value="problems" className="pt-3">
          <Problems />
        </TabsContent>
        <TabsContent value="contributions" className="pt-3">
          <Contributions />
        </TabsContent>
        <TabsContent value="challengers" className="pt-3">
          <Challengers />
        </TabsContent>
        <TabsContent value="submissions" className="pt-3">
          <Recent />
        </TabsContent>
      </Tabs>
    </>
  );
}
