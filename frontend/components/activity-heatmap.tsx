"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

const WEEKS = 53;
const LEVELS = ["bg-muted", "bg-foreground/25", "bg-foreground/50", "bg-foreground/75", "bg-foreground"];

const iso = (d: Date) => d.toISOString().slice(0, 10);

/** Submissions per day over the last year, one column per week (UTC days). */
export function ActivityHeatmap({ userId }: { userId: number | string }) {
  const { data } = useQuery({
    queryKey: ["activity", String(userId)],
    queryFn: () => api<{ day: string; count: number }[]>(`/users/${userId}/activity`),
  });
  if (!data) return null;
  const counts = new Map(data.map((d) => [d.day, d.count]));
  const max = Math.max(1, ...counts.values());

  // last cell is today; the grid starts on the Sunday 52 weeks before this week's Sunday
  const today = new Date(iso(new Date()));
  const start = new Date(today);
  start.setUTCDate(today.getUTCDate() - today.getUTCDay() - (WEEKS - 1) * 7);
  const days = Array.from({ length: WEEKS * 7 }, (_, i) => {
    const d = new Date(start);
    d.setUTCDate(start.getUTCDate() + i);
    return d;
  }).filter((d) => d <= today);
  const total = data.reduce((a, d) => a + d.count, 0);

  return (
    <figure>
      <div
        className="grid w-full max-w-3xl grid-flow-col grid-rows-7 gap-[3px] overflow-x-auto"
        role="img"
        aria-label={`${total} submissions in the last year`}
      >
        {days.map((d) => {
          const n = counts.get(iso(d)) ?? 0;
          const level = n === 0 ? 0 : Math.ceil((n / max) * (LEVELS.length - 1));
          return (
            <div
              key={iso(d)}
              title={`${iso(d)}: ${n} submission${n === 1 ? "" : "s"}`}
              className={`aspect-square min-w-2 rounded-[2px] ${LEVELS[level]}`}
            />
          );
        })}
      </div>
      <figcaption className="mt-2 text-xs text-muted-foreground">
        {total} submission{total === 1 ? "" : "s"} in the last year. Darker squares are busier days.
      </figcaption>
    </figure>
  );
}
