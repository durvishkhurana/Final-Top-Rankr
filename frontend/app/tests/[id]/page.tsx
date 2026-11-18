"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useRef, useState } from "react";

import { IntegrityMonitor } from "@/components/integrity-monitor";
import { ErrorNote, Loading } from "@/components/state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, post, put } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { AnswerView, AttemptView, Exam } from "@/lib/types";

function Consent({ exam, onStart }: { exam: Exam; onStart: () => void }) {
  const [camera, setCamera] = useState(false);
  const start = useMutation({
    mutationFn: () => post<AttemptView>(`/tests/${exam.id}/attempt`, { consent: true, camera_consent: camera }),
    onSuccess: onStart,
  });
  return (
    <section className="max-w-2xl space-y-4 rounded-xl border p-5 text-sm">
      <h2 className="text-lg font-medium">Before you start</h2>
      <p>While you take this test, your browser records these signals and sends them to your instructor as a list of events (time, type, duration):</p>
      <ul className="list-disc space-y-1 pl-6">
        <li>switching to another tab or window, and leaving full screen;</li>
        <li>copying and pasting (only how many characters, not the text);</li>
        <li>how long you spend on each answer.</li>
      </ul>
      {exam.camera_checks && (
        <>
          <p>
            If you allow it, face detection also runs <strong>on this device only</strong>. It notes when no face is
            visible for more than 5 seconds, when two faces are visible, or when you look away for a few seconds. No
            image or video ever leaves your browser; the detection model is downloaded from Google&apos;s servers.
          </p>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={camera} onChange={(e) => setCamera(e.target.checked)} /> Allow camera checks
            (optional)
          </label>
        </>
      )}
      <p>
        Nothing here fails you automatically: your instructor reviews the signals together with your answers. The event
        log is deleted automatically after the retention period. See the{" "}
        <a href="https://github.com/durvishkhurana/Final-Top-Rankr/blob/main/docs/PRIVACY.md" className="underline">
          privacy notice
        </a>
        .
      </p>
      {start.error && <ErrorNote error={start.error} />}
      <Button disabled={start.isPending} onClick={() => start.mutate()}>
        I understand, start the test
      </Button>
    </section>
  );
}

function AnswerBox({ a, open }: { a: AnswerView; open: boolean }) {
  const [value, setValue] = useState(a.response);
  const [followUp, setFollowUp] = useState(a.follow_up);
  const [followValue, setFollowValue] = useState(a.follow_up_response);
  const focused = useRef(0);
  const pasted = useRef(0);
  const save = useMutation({
    mutationFn: (response: string) => {
      const time_ms = focused.current ? Date.now() - focused.current : 0;
      focused.current = 0;
      const paste_chars = pasted.current;
      pasted.current = 0;
      return put<{ follow_up: string }>(`/answers/${a.id}`, { response, time_ms, paste_chars });
    },
    onSuccess: (r) => setFollowUp(r.follow_up),
  });
  const saveFollow = useMutation({ mutationFn: (response: string) => put(`/answers/${a.id}/follow-up`, { response }) });
  const track = {
    onFocus: () => (focused.current = Date.now()),
    onPaste: (e: React.ClipboardEvent) => (pasted.current += e.clipboardData.getData("text").length),
  };
  const id = `answer-${a.id}`;

  return (
    <li className="space-y-3 rounded-xl border p-4">
      <div className="flex gap-2 text-sm">
        <span className="font-medium">{a.prompt}</span>
        <span className="ml-auto shrink-0 text-muted-foreground">
          {a.score != null ? `${a.score} / ${a.max_score}` : `${a.max_score} pt`}
        </span>
      </div>
      {a.kind === "mcq" ? (
        <fieldset className="space-y-1 text-sm" disabled={!open}>
          <legend className="sr-only">Choices</legend>
          {a.choices?.map((c, i) => (
            <label key={i} className="flex items-center gap-2">
              <input
                type="radio"
                name={id}
                checked={value === String(i)}
                onChange={() => {
                  setValue(String(i));
                  save.mutate(String(i));
                }}
              />
              {c}
            </label>
          ))}
        </fieldset>
      ) : a.kind === "numeric" ? (
        <div className="max-w-xs space-y-1">
          <Label htmlFor={id}>Your answer</Label>
          <Input
            id={id}
            inputMode="decimal"
            value={value}
            disabled={!open}
            onChange={(e) => setValue(e.target.value)}
            onBlur={() => value !== a.response && save.mutate(value)}
            {...track}
          />
        </div>
      ) : (
        <div className="space-y-1">
          <Label htmlFor={id}>Your answer, in one line</Label>
          <Input
            id={id}
            value={value}
            maxLength={500}
            disabled={!open}
            onChange={(e) => setValue(e.target.value)}
            onBlur={() => value.trim() && save.mutate(value)}
            {...track}
          />
        </div>
      )}
      {save.isPending && <p className="text-xs text-muted-foreground">Saving…</p>}
      {save.error && <ErrorNote error={save.error} />}
      {followUp && (
        <div className="space-y-1">
          <Label htmlFor={`${id}-follow`}>Follow-up: {followUp}</Label>
          <Textarea
            id={`${id}-follow`}
            rows={2}
            value={followValue}
            disabled={!open}
            onChange={(e) => setFollowValue(e.target.value)}
            onBlur={() => followValue.trim() && saveFollow.mutate(followValue)}
            {...track}
          />
        </div>
      )}
      {a.rationale && <p className="text-xs text-muted-foreground">Feedback: {a.rationale}</p>}
    </li>
  );
}

export default function TakeTestPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [now] = useState(() => Date.now());
  const exam = useQuery({ queryKey: ["test", id], queryFn: () => api<Exam>(`/tests/${id}`) });
  const attemptId = exam.data?.attempt?.id;
  const attempt = useQuery({
    queryKey: ["attempt", attemptId],
    queryFn: () => api<AttemptView>(`/attempts/${attemptId}`),
    enabled: !!attemptId,
  });
  const submit = useMutation({
    mutationFn: () => post<AttemptView>(`/attempts/${attemptId}/submit`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["test", id] }),
  });

  if (exam.isPending || (attemptId && attempt.isPending)) return <Loading />;
  if (exam.error) return <ErrorNote error={exam.error} />;
  if (attempt.error) return <ErrorNote error={attempt.error} />;
  const t = exam.data;
  const a = attempt.data;
  const open = a?.status === "in_progress" && t.status === "live";

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-muted-foreground">
          <Link href="/tests" className="hover:underline">
            Tests
          </Link>{" "}
          / {t.course_title}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{t.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Open {fmtDate(t.starts_at)} to {fmtDate(t.ends_at)} · {t.max_total} points
        </p>
        {t.description && <p className="mt-2 max-w-3xl text-sm">{t.description}</p>}
      </div>

      {!a ? (
        t.status === "live" && now >= Date.parse(t.starts_at) && now <= Date.parse(t.ends_at) ? (
          <Consent exam={t} onStart={() => queryClient.invalidateQueries({ queryKey: ["test", id] })} />
        ) : (
          <p className="text-sm text-muted-foreground">This test is not open.</p>
        )
      ) : (
        <>
          {open && (
            <div className="flex flex-wrap items-center gap-3">
              <IntegrityMonitor attemptId={a.id} camera={a.camera_consent} />
              <Button variant="outline" size="sm" onClick={() => document.documentElement.requestFullscreen().catch(() => undefined)}>
                Full screen
              </Button>
            </div>
          )}
          {!open && (
            <p className="rounded-lg border p-3 text-sm" role="status">
              {a.status === "in_progress"
                ? "The test has closed."
                : a.total != null
                  ? `Graded: ${a.total} of ${t.max_total} points.`
                  : "Handed in. Grades appear here when your instructor closes the test."}
            </p>
          )}
          <ol className="space-y-3">
            {a.answers.map((ans) => (
              <AnswerBox key={ans.id} a={ans} open={open} />
            ))}
          </ol>
          {open && (
            <>
              {submit.error && <ErrorNote error={submit.error} />}
              <Button
                disabled={submit.isPending}
                onClick={() => window.confirm("Hand in your answers? You cannot change them afterwards.") && submit.mutate()}
              >
                Hand in
              </Button>
            </>
          )}
        </>
      )}
    </div>
  );
}
