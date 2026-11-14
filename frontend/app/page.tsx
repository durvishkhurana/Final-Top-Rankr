"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { fmtInt } from "@/lib/format";
import type { Stats } from "@/lib/types";

const POINTS = [
  [
    "Submit an algorithm, not an answer",
    "You write one Python function, optimize(f, …). The platform calls it; you never see the function it is minimising.",
  ],
  [
    "Same budget for everyone",
    "Every run gets the same number of evaluations, on the same hidden instances, with the same seeds, inside a sandbox on the server.",
  ],
  [
    "Scored on the whole run",
    "The score rewards how good the final result is and how quickly it was reached, and is reported with its spread across seeds.",
  ],
];

export default function Home() {
  const stats = useQuery({ queryKey: ["stats"], queryFn: () => api<Stats>("/stats") });
  const figures = stats.data && [
    ["Problems", stats.data.problems],
    ["Submissions", stats.data.submissions],
    ["Runs judged", stats.data.runs],
    ["Function evaluations", stats.data.evaluations],
  ] as const;

  return (
    <div className="space-y-12">
      <section className="max-w-3xl pt-6">
        <h1 className="text-4xl font-semibold tracking-tight">
          An online judge for optimization algorithms
        </h1>
        <p className="mt-4 text-lg text-muted-foreground">
          Kaggle compares models on datasets. TopRanker compares optimizers on hidden black-box
          functions, under identical evaluation budgets, with every run executed and verified on
          the server.
        </p>
        <div className="mt-6 flex gap-3">
          <Link href="/problems" className={buttonVariants({ size: "lg" })}>
            Browse problems
          </Link>
          <Link href="/leaderboard" className={buttonVariants({ variant: "outline", size: "lg" })}>
            Leaderboard
          </Link>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {POINTS.map(([title, text]) => (
          <Card key={title}>
            <CardHeader>
              <CardTitle>{title}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{text}</CardContent>
          </Card>
        ))}
      </section>

      {figures && (
        <section aria-label="Platform totals" className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {figures.map(([label, value]) => (
            <div key={label} className="rounded-xl border p-4">
              <div className="text-2xl font-semibold tabular-nums">{fmtInt(value)}</div>
              <div className="text-sm text-muted-foreground">{label}</div>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
