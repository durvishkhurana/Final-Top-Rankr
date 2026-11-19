"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Empty, ErrorNote, Loading, PageTitle } from "@/components/state";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import type { GlobalRow, SetterRow } from "@/lib/types";

type By = "user" | "country" | "institution";

function Board({ by }: { by: By }) {
  const { data, error, isPending } = useQuery({
    queryKey: ["leaderboard", by],
    queryFn: () => api<GlobalRow[]>(`/leaderboard?by=${by}`),
  });
  if (isPending) return <Loading />;
  if (error) return <ErrorNote error={error} />;
  if (data.length === 0) return <Empty>Nothing to rank yet.</Empty>;
  const people = by === "user";

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-12">#</TableHead>
          <TableHead>{people ? "Name" : by === "country" ? "Country" : "Institution"}</TableHead>
          {people && <TableHead>Institution</TableHead>}
          {people && <TableHead>Country</TableHead>}
          <TableHead className="text-right">{people ? "Rating" : "Mean rating"}</TableHead>
          <TableHead className="text-right">{people ? "Problems" : "Rated members"}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((row) => (
          <TableRow key={row.key}>
            <TableCell className="tabular-nums">{row.rank}</TableCell>
            <TableCell>
              {people ? (
                <Link href={`/profile/${row.key}`} className="hover:underline">
                  {row.name}
                </Link>
              ) : (
                row.name
              )}
            </TableCell>
            {people && <TableCell>{row.institution || "–"}</TableCell>}
            {people && <TableCell>{row.country || "–"}</TableCell>}
            <TableCell className="text-right font-medium tabular-nums">
              {row.rating.toFixed(0)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {people ? row.problems : row.members}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** People whose contributed problems were approved and are live. */
function Setters() {
  const { data, error, isPending } = useQuery({
    queryKey: ["leaderboard", "setters"],
    queryFn: () => api<SetterRow[]>("/leaderboard/setters"),
  });
  if (isPending) return <Loading />;
  if (error) return <ErrorNote error={error} />;
  if (data.length === 0) return <Empty>No contributed problems have been approved yet.</Empty>;

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">#</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Institution</TableHead>
            <TableHead>Country</TableHead>
            <TableHead className="text-right">Problems</TableHead>
            <TableHead className="text-right">Solvers</TableHead>
            <TableHead className="text-right">Submissions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((row) => (
            <TableRow key={row.user_id}>
              <TableCell className="tabular-nums">{row.rank}</TableCell>
              <TableCell>
                <Link href={`/profile/${row.user_id}`} className="hover:underline">
                  {row.name}
                </Link>
              </TableCell>
              <TableCell>{row.institution || "–"}</TableCell>
              <TableCell>{row.country || "–"}</TableCell>
              <TableCell className="text-right font-medium tabular-nums">{row.problems}</TableCell>
              <TableCell className="text-right tabular-nums">{row.solvers}</TableCell>
              <TableCell className="text-right tabular-nums">{row.submissions}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="mt-2 text-xs text-muted-foreground">
        Ranked by approved problems in the catalogue, then by solvers: the people other than the setter with a
        judged submission on them. Baselines are not counted.
      </p>
    </>
  );
}

export default function LeaderboardPage() {
  return (
    <>
      <PageTitle title="Leaderboard">
        A rating is the sum, over problems, of a person&apos;s best score on that problem (0 to
        1000 each). Countries and institutions are ranked by the mean rating of their rated
        members. Baselines are not ranked here; they appear on each problem&apos;s own
        leaderboard.
      </PageTitle>
      <Tabs defaultValue="user">
        <TabsList>
          <TabsTrigger value="user">People</TabsTrigger>
          <TabsTrigger value="country">Countries</TabsTrigger>
          <TabsTrigger value="institution">Institutions</TabsTrigger>
          <TabsTrigger value="setters">Problem setters</TabsTrigger>
        </TabsList>
        {(["user", "country", "institution"] as const).map((by) => (
          <TabsContent key={by} value={by} className="pt-3">
            <Board by={by} />
          </TabsContent>
        ))}
        <TabsContent value="setters" className="pt-3">
          <Setters />
        </TabsContent>
      </Tabs>
    </>
  );
}
