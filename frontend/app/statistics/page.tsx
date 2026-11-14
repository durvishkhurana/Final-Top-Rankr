"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ErrorNote, Loading, PageTitle } from "@/components/state";
import { api } from "@/lib/api";
import { fmtInt } from "@/lib/format";
import type { Stats } from "@/lib/types";

function Bars({ data, x, label }: { data: object[]; x: string; label: string }) {
  return (
    <figure>
      <div className="h-64 w-full">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border" />
            <XAxis dataKey={x} fontSize={11} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} fontSize={12} width={36} />
            <Tooltip />
            <Bar dataKey="count" name="Submissions" fill="var(--foreground)" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-muted-foreground">{label}</figcaption>
    </figure>
  );
}

export default function StatisticsPage() {
  const { data, error, isPending } = useQuery({
    queryKey: ["stats"],
    queryFn: () => api<Stats>("/stats"),
  });
  if (isPending) return <Loading />;
  if (error) return <ErrorNote error={error} />;

  const figures = [
    ["Registered users", data.users],
    ["Active problems", data.problems],
    ["Submissions", data.submissions],
    ["Runs judged", data.runs],
    ["Function evaluations", data.evaluations],
    ["Submissions that failed to judge", data.by_status.failed ?? 0],
  ] as const;

  return (
    <>
      <PageTitle title="Statistics">Counts taken directly from the judge&apos;s records.</PageTitle>
      <section aria-label="Totals" className="mb-10 grid grid-cols-2 gap-4 md:grid-cols-3">
        {figures.map(([label, value]) => (
          <div key={label} className="rounded-xl border p-4">
            <div className="text-2xl font-semibold tabular-nums">{fmtInt(value)}</div>
            <div className="text-sm text-muted-foreground">{label}</div>
          </div>
        ))}
      </section>
      <section className="grid gap-10 lg:grid-cols-2">
        <div>
          <h2 className="mb-2 text-lg font-medium">Submissions per day</h2>
          <Bars
            data={data.per_day.map((d) => ({ ...d, day: d.day.slice(5) }))}
            x="day"
            label="Last 30 days (UTC), baselines included."
          />
        </div>
        <div>
          <h2 className="mb-2 text-lg font-medium">Submissions per problem</h2>
          <Bars data={data.per_problem} x="problem_id" label="All time, baselines included." />
        </div>
      </section>
    </>
  );
}
