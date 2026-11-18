"use client";

import Link from "next/link";
import { useState } from "react";

import { useProblems } from "@/components/problem-picker";
import { Empty, ErrorNote, Loading, PageTitle } from "@/components/state";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const LEVELS = ["All", "Easy", "Medium", "Hard"];

export default function ProblemsPage() {
  const { data, error, isPending } = useProblems();
  const [level, setLevel] = useState("All");
  const shown = data?.filter((p) => level === "All" || p.level === level) ?? [];
  const categories = [...new Set(shown.map((p) => p.category))];

  return (
    <>
      <PageTitle title="Problems">
        Each problem is a hidden function to minimise. You see a description, the search box and
        the dimensions; the function itself stays on the server and every run uses a shifted and
        rotated instance of it.
      </PageTitle>
      <div className="mb-6 flex gap-2" role="group" aria-label="Filter by level">
        {LEVELS.map((l) => (
          <button
            key={l}
            onClick={() => setLevel(l)}
            aria-pressed={level === l}
            className={`rounded-full border px-3 py-1 text-sm ${level === l ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}
          >
            {l}
          </button>
        ))}
      </div>
      {isPending && <Loading />}
      {error && <ErrorNote error={error} />}
      {data && shown.length === 0 && <Empty>No problems match this filter.</Empty>}
      {categories.map((category) => (
        <section key={category} className="mb-8">
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
            {category}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {shown
              .filter((p) => p.category === category)
              .map((p) => (
                <Link key={p.id} href={`/problems/${p.id}`} className="group">
                  <Card className="h-full transition-colors group-hover:border-foreground/40">
                    <CardHeader>
                      <CardDescription className="flex items-center justify-between">
                        <span className="font-mono">{p.id}</span>
                        <Badge variant={p.level === "Hard" ? "default" : "secondary"}>
                          {p.level}
                        </Badge>
                      </CardDescription>
                      <CardTitle>{p.name}</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm text-muted-foreground">
                      <p>{p.summary}</p>
                      <p className="text-xs">
                        {p.submissions} submission{p.submissions === 1 ? "" : "s"} · dimensions{" "}
                        {p.dims.join(", ")}
                      </p>
                    </CardContent>
                  </Card>
                </Link>
              ))}
          </div>
        </section>
      ))}
    </>
  );
}
