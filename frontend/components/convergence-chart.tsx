"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Run } from "@/lib/types";

function quantile(sorted: number[], q: number): number {
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

const pow = (v: number) => `1e${Math.round(Math.log10(v))}`;

/** Best-so-far precision against evaluations: median line with an interquartile band
 *  across all successful runs, both axes logarithmic. */
export function ConvergenceChart({ checkpoints, runs }: { checkpoints: number[]; runs: Run[] }) {
  const ok = runs.filter((r) => r.status === "ok");
  const data = checkpoints.flatMap((evals, k) => {
    const values = ok
      .map((r) => r.precision_trace[k])
      .filter((v): v is number => v != null)
      .sort((a, b) => a - b);
    if (values.length === 0) return [];
    return [{ evals, median: quantile(values, 0.5), band: [quantile(values, 0.25), quantile(values, 0.75)] }];
  });
  if (data.length === 0) {
    return <p className="py-6 text-sm text-muted-foreground">No successful runs to plot.</p>;
  }

  // powers of ten up to the budget, plus the budget itself
  const last = data[data.length - 1].evals;
  const ticks = [1, 10, 100, 1000, 10000, 100000].filter((t) => t < last * 0.6).concat(last);

  return (
    <figure>
      <div className="h-72 w-full">
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 16, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis
              dataKey="evals"
              type="number"
              scale="log"
              domain={["dataMin", "dataMax"]}
              ticks={ticks}
              tickFormatter={(v: number) => v.toLocaleString()}
              label={{ value: "Evaluations", position: "insideBottom", offset: -8, fontSize: 12 }}
              fontSize={12}
            />
            <YAxis
              scale="log"
              domain={[1e-8, "auto"]}
              allowDataOverflow
              tickFormatter={pow}
              label={{ value: "Precision", angle: -90, position: "insideLeft", fontSize: 12 }}
              fontSize={12}
            />
            <Tooltip
              formatter={(v) =>
                Array.isArray(v)
                  ? v.map((x) => Number(x).toExponential(2)).join(" – ")
                  : Number(v).toExponential(2)
              }
              labelFormatter={(v) => `${Number(v).toLocaleString()} evaluations`}
            />
            <Area
              dataKey="band"
              name="Interquartile range"
              stroke="none"
              fill="var(--foreground)"
              fillOpacity={0.15}
              isAnimationActive={false}
            />
            <Line
              dataKey="median"
              name="Median"
              stroke="var(--foreground)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-muted-foreground">
        Best value found so far minus the reference value, over {ok.length} successful run
        {ok.length === 1 ? "" : "s"}. Line: median. Band: 25th to 75th percentile. Lower is better.
      </figcaption>
    </figure>
  );
}
