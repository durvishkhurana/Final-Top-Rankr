"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorNote } from "@/components/state";
import { Button } from "@/components/ui/button";
import { api, post } from "@/lib/api";
import type { AiNote, AiStatus } from "@/lib/types";

const LABELS: Record<string, string> = {
  family: "Closest family",
  population_based: "Population based",
  mutation: "Mutation",
  crossover: "Crossover",
  selection: "Selection",
  restarts: "Restarts",
  local_search: "Local search",
  summary: "Summary",
  diagnosis: "What happened",
  suggestion: "One thing to try",
};

function Note({ note }: { note: AiNote }) {
  return (
    <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[10rem_1fr]">
      {Object.entries(note.content).map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted-foreground">{LABELS[k] ?? k}</dt>
          <dd>{typeof v === "boolean" ? (v ? "yes" : "no") : String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Analysis of the code and a diagnosis of the runs, for the author. The model sees the
 *  code and summary statistics computed by the judge, never the hidden function. */
export function AiNotes({ submissionId, judged }: { submissionId: number; judged: boolean }) {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["ai-status"], queryFn: () => api<AiStatus>("/ai/status") });
  const notes = useQuery({
    queryKey: ["notes", submissionId],
    queryFn: () => api<AiNote[]>(`/submissions/${submissionId}/notes`),
  });
  const ask = useMutation({
    mutationFn: (kind: "analysis" | "coach") => post<AiNote>(`/submissions/${submissionId}/${kind}`),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["notes", submissionId] });
      queryClient.invalidateQueries({ queryKey: ["ai-status"] });
    },
  });

  if (status.data && !status.data.enabled) {
    return <p className="text-sm text-muted-foreground">AI features are disabled on this server.</p>;
  }
  const have = new Set(notes.data?.map((n) => n.kind));
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        AI-assisted assessment. It can be wrong; the score and the charts above come from the judge.
        {status.data && ` ${status.data.remaining_today} requests left today.`}
      </p>
      {notes.data?.map((n) => (
        <div key={n.kind} className="rounded-lg border p-3">
          <h3 className="mb-2 text-sm font-medium">
            {n.kind === "analysis" ? "What this algorithm is" : "Run diagnosis"}
          </h3>
          <Note note={n} />
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        {!have.has("analysis") && (
          <Button variant="outline" size="sm" disabled={ask.isPending} onClick={() => ask.mutate("analysis")}>
            Explain my algorithm
          </Button>
        )}
        {judged && !have.has("coach") && (
          <Button variant="outline" size="sm" disabled={ask.isPending} onClick={() => ask.mutate("coach")}>
            Diagnose the runs
          </Button>
        )}
      </div>
      {ask.isPending && <p className="text-sm text-muted-foreground">Asking the model…</p>}
      {ask.error && <ErrorNote error={ask.error} />}
    </div>
  );
}
