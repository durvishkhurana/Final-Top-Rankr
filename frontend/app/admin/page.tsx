"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ErrorNote, Loading, PageTitle } from "@/components/state";
import { SubmissionList } from "@/components/submission-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, patch, post } from "@/lib/api";
import { useMe } from "@/lib/auth";
import type { AdminUser, Problem, Role, Submission } from "@/lib/types";

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
  if (problems.isPending) return <Loading />;
  if (problems.error) return <ErrorNote error={problems.error} />;
  return (
    <>
      {note && (
        <p role="status" className="mb-3 rounded-lg border p-3 text-sm">
          {note}
        </p>
      )}
      {(setActive.error || baselines.error) && (
        <ErrorNote error={setActive.error ?? baselines.error} />
      )}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Problem</TableHead>
            <TableHead>Visible</TableHead>
            <TableHead>Run baselines at dimension</TableHead>
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
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
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
          <TabsTrigger value="submissions">Recent submissions</TabsTrigger>
        </TabsList>
        <TabsContent value="users" className="pt-3">
          <Users myId={me.id} />
        </TabsContent>
        <TabsContent value="problems" className="pt-3">
          <Problems />
        </TabsContent>
        <TabsContent value="submissions" className="pt-3">
          <Recent />
        </TabsContent>
      </Tabs>
    </>
  );
}
