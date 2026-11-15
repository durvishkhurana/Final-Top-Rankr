"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { CodeEditor } from "@/components/code-editor";
import { Empty, ErrorNote, Loading, PageTitle } from "@/components/state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, post } from "@/lib/api";
import { useMe } from "@/lib/auth";
import type { Contribution } from "@/lib/types";
import { STATUS_TEXT, SmokeChecks } from "@/components/smoke-checks";

const STARTER = `import numpy as np


def f(X):
    """X has shape (n, dim). Return n values; lower is better."""
    return np.sum(X ** 2, axis=1)
`;

const MAX_IMAGE = 2_000_000;

function Builder({ onDone }: { onDone: () => void }) {
  const [image, setImage] = useState<File | null>(null);
  const [tooBig, setTooBig] = useState(false);
  const build = useMutation({
    mutationFn: async (text: string) => {
      let image_base64 = "";
      if (image) {
        const bytes = new Uint8Array(await image.arrayBuffer());
        image_base64 = btoa(Array.from(bytes, (b) => String.fromCharCode(b)).join(""));
      }
      return post<Contribution>("/contributions/build", {
        text,
        image_base64,
        image_mime: image?.type || "image/png",
      });
    },
    onSuccess: onDone,
  });
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        build.mutate(String(new FormData(e.currentTarget).get("text")));
      }}
    >
      <div className="space-y-1">
        <Label htmlFor="text">Describe the function in words</Label>
        <Textarea
          id="text"
          name="text"
          required
          rows={4}
          placeholder="e.g. Rastrigin with a narrow valley added along the first axis, box -5 to 5"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="image">Or add a picture of the formula (PNG or JPEG, up to 2 MB)</Label>
        <Input
          id="image"
          type="file"
          accept="image/png,image/jpeg"
          onChange={(e) => {
            const file = e.target.files?.[0] ?? null;
            setTooBig(!!file && file.size > MAX_IMAGE);
            setImage(file && file.size <= MAX_IMAGE ? file : null);
          }}
        />
        {tooBig && <p className="text-sm text-destructive">That image is larger than 2 MB.</p>}
      </div>
      {build.error && <ErrorNote error={build.error} />}
      <Button type="submit" disabled={build.isPending}>
        {build.isPending ? "Drafting…" : "Draft with AI"}
      </Button>
      <p className="text-xs text-muted-foreground">
        The draft is AI-assisted. It goes through the same sandboxed smoke test and admin review as a
        hand-written contribution.
      </p>
    </form>
  );
}

function Manual({ onDone }: { onDone: () => void }) {
  const [source, setSource] = useState(STARTER);
  const send = useMutation({
    mutationFn: (form: FormData) =>
      post<Contribution>("/contributions", {
        name: form.get("name"),
        summary: form.get("summary"),
        description: form.get("description"),
        source,
        lower: Number(form.get("lower")),
        upper: Number(form.get("upper")),
        dims: String(form.get("dims"))
          .split(",")
          .map((d) => Number(d.trim()))
          .filter(Boolean),
        level: form.get("level"),
        tags: String(form.get("tags"))
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      }),
    onSuccess: onDone,
  });
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        send.mutate(new FormData(e.currentTarget));
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="name">Name</Label>
          <Input id="name" name="name" required maxLength={100} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="summary">One-line summary</Label>
          <Input id="summary" name="summary" required maxLength={300} />
        </div>
      </div>
      <div className="space-y-1">
        <Label htmlFor="description">Description shown to participants</Label>
        <Textarea id="description" name="description" rows={3} maxLength={5000} />
      </div>
      <div className="grid gap-3 sm:grid-cols-5">
        <div className="space-y-1">
          <Label htmlFor="lower">Lower bound</Label>
          <Input id="lower" name="lower" type="number" step="any" defaultValue={-5} required />
        </div>
        <div className="space-y-1">
          <Label htmlFor="upper">Upper bound</Label>
          <Input id="upper" name="upper" type="number" step="any" defaultValue={5} required />
        </div>
        <div className="space-y-1">
          <Label htmlFor="dims">Dimensions</Label>
          <Input id="dims" name="dims" defaultValue="5, 10" required />
        </div>
        <div className="space-y-1">
          <Label htmlFor="level">Level</Label>
          <select id="level" name="level" defaultValue="Medium" className="h-8 w-full rounded-lg border bg-background px-2 text-sm">
            <option>Easy</option>
            <option>Medium</option>
            <option>Hard</option>
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="tags">Tags</Label>
          <Input id="tags" name="tags" placeholder="multimodal, noisy" />
        </div>
      </div>
      <div className="space-y-1">
        <span className="text-sm font-medium">Fitness function</span>
        <CodeEditor value={source} onChange={setSource} height={240} />
      </div>
      {send.error && <ErrorNote error={send.error} />}
      <Button type="submit" disabled={send.isPending}>
        Submit for review
      </Button>
    </form>
  );
}

export default function ContributePage() {
  const me = useMe();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"manual" | "ai">("manual");
  const mine = useQuery({
    queryKey: ["contributions"],
    queryFn: () => api<Contribution[]>("/contributions"),
    enabled: !!me,
    refetchInterval: (q) => (q.state.data?.some((c) => c.status === "testing") ? 2000 : false),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["contributions"] });

  if (me === undefined) return <Loading />;
  if (!me)
    return (
      <ErrorNote error={new Error("Log in to contribute a problem.")} />
    );
  return (
    <div className="space-y-8">
      <PageTitle title="Contribute a problem">
        Propose a fitness function. It is checked in a sandbox container (it loads, returns finite
        values, is deterministic and not constant) and then reviewed by an admin before it appears in
        the catalogue. Instances shift it the same way as the built-in problems.
      </PageTitle>
      <div className="flex gap-2">
        <Button variant={mode === "manual" ? "default" : "outline"} size="sm" onClick={() => setMode("manual")}>
          Write the code
        </Button>
        <Button variant={mode === "ai" ? "default" : "outline"} size="sm" onClick={() => setMode("ai")}>
          Describe it, draft with AI
        </Button>
      </div>
      {mode === "manual" ? <Manual onDone={refresh} /> : <Builder onDone={refresh} />}

      <section>
        <h2 className="mb-2 text-lg font-medium">Your contributions</h2>
        {mine.isPending ? (
          <Loading rows={2} />
        ) : mine.error ? (
          <ErrorNote error={mine.error} />
        ) : mine.data.length === 0 ? (
          <Empty>Nothing yet.</Empty>
        ) : (
          <ul className="space-y-3">
            {mine.data.map((c) => (
              <li key={c.id} className="rounded-lg border p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="font-medium">{c.name}</span>
                  <Badge variant={c.status === "failed" || c.status === "rejected" ? "destructive" : "outline"}>
                    {STATUS_TEXT[c.status] ?? c.status}
                  </Badge>
                  {c.ai_built && <Badge variant="outline">AI-drafted</Badge>}
                  {c.problem_id && (
                    <Link href={`/problems/${c.problem_id}`} className="text-sm underline">
                      {c.problem_id}
                    </Link>
                  )}
                </div>
                <SmokeChecks item={c} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
