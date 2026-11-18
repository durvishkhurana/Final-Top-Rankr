"use client";

import { useQuery } from "@tanstack/react-query";
import { useId } from "react";

import { api } from "@/lib/api";
import type { Problem } from "@/lib/types";
import { selectClass } from "@/lib/utils";

/** The active problem catalogue, shared by every page that lists it. */
export function useProblems() {
  return useQuery({ queryKey: ["problems"], queryFn: () => api<Problem[]>("/problems") });
}

/** A problem, then one of its dimensions. Choosing a problem selects its first dimension. */
export function ProblemPicker({
  problems,
  problemId,
  dim,
  onChange,
}: {
  problems: Problem[];
  problemId: string;
  dim: number | undefined;
  onChange: (problemId: string, dim: number) => void;
}) {
  const id = useId();
  const problem = problems.find((p) => p.id === problemId);
  return (
    <>
      <label htmlFor={`${id}-problem`}>Problem</label>
      <select
        id={`${id}-problem`}
        className={selectClass}
        value={problemId}
        onChange={(e) => onChange(e.target.value, problems.find((p) => p.id === e.target.value)!.dims[0])}
      >
        <option value="" disabled>
          choose…
        </option>
        {problems.map((p) => (
          <option key={p.id} value={p.id}>
            {p.id} {p.name}
          </option>
        ))}
      </select>
      {problem && (
        <>
          <label htmlFor={`${id}-dim`}>Dimension</label>
          <select
            id={`${id}-dim`}
            className={selectClass}
            value={dim ?? problem.dims[0]}
            onChange={(e) => onChange(problemId, Number(e.target.value))}
          >
            {problem.dims.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </>
      )}
    </>
  );
}
