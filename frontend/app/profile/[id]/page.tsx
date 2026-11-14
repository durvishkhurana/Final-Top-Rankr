"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ActivityHeatmap } from "@/components/activity-heatmap";
import { ErrorNote, Loading } from "@/components/state";
import { SubmissionList } from "@/components/submission-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, patch } from "@/lib/api";
import { useMe } from "@/lib/auth";
import type { Profile } from "@/lib/types";

function EditProfile({ profile, onDone }: { profile: Profile; onDone: () => void }) {
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: (body: Record<string, FormDataEntryValue>) => patch("/users/me", body),
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      onDone();
    },
  });
  return (
    <form
      className="max-w-md space-y-3 rounded-xl border p-4"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(Object.fromEntries(new FormData(e.currentTarget)));
      }}
    >
      {(["name", "country", "institution"] as const).map((field) => (
        <div key={field} className="space-y-1.5">
          <Label htmlFor={field} className="capitalize">
            {field}
          </Label>
          <Input id={field} name={field} defaultValue={profile[field]} required={field === "name"} />
        </div>
      ))}
      <div className="space-y-1.5">
        <Label htmlFor="bio">About</Label>
        <Textarea id="bio" name="bio" defaultValue={profile.bio} maxLength={500} />
      </div>
      {save.error && <ErrorNote error={save.error} />}
      <div className="flex gap-2">
        <Button type="submit" disabled={save.isPending}>
          Save
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export default function ProfilePage() {
  const { id } = useParams<{ id: string }>();
  const me = useMe();
  const [editing, setEditing] = useState(false);
  const { data: p, error, isPending } = useQuery({
    queryKey: ["profile", id],
    queryFn: () => api<Profile>(`/users/${id}`),
  });
  if (isPending) return <Loading />;
  if (error) return <ErrorNote error={error} />;

  const figures = [
    ["Rating", p.rating.toFixed(0)],
    ["Global rank", p.rank ? `#${p.rank}` : "Unranked"],
    ["Problems attempted", p.problems_attempted],
    ["Submissions", p.submissions],
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-3 text-2xl font-semibold tracking-tight">
          {p.name} {p.role !== "student" && <Badge variant="secondary">{p.role}</Badge>}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {[p.institution, p.country].filter(Boolean).join(" · ") || "No affiliation given"} ·
          joined {new Date(p.created_at).toLocaleDateString()}
        </p>
        {p.bio && <p className="mt-3 max-w-2xl text-sm">{p.bio}</p>}
        {me?.id === p.id && !editing && (
          <Button variant="outline" size="sm" className="mt-3" onClick={() => setEditing(true)}>
            Edit profile
          </Button>
        )}
      </div>
      {editing && <EditProfile profile={p} onDone={() => setEditing(false)} />}

      <section aria-label="Summary" className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {figures.map(([label, value]) => (
          <div key={label} className="rounded-xl border p-4">
            <div className="text-xl font-semibold tabular-nums">{value}</div>
            <div className="text-sm text-muted-foreground">{label}</div>
          </div>
        ))}
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium">Activity</h2>
        <ActivityHeatmap userId={p.id} />
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium">Recent submissions</h2>
        <SubmissionList rows={p.recent} empty="No submissions yet." />
      </section>
    </div>
  );
}
