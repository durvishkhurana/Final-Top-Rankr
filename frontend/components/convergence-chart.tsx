"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PALETTE } from "@/components/solution-view";
import { evalTicks } from "@/lib/format";
import type { Curve, Run } from "@/lib/types";

function quantile(sorted: number[], q: number): number {
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

const pow = (v: number) => `1e${Math.round(Math.log10(v))}`;

/** Best-so-far precision against evaluations: median line with an interquartile band
 *  across all successful runs, both axes logarithmic. Overlays are the median curves of
 *  other entries on the same problem and dimension. */
export function ConvergenceChart({
  checkpoints,
  runs,
  overlays = [],
}: {
  checkpoints: number[];
  runs: Run[];
  overlays?: Curve[];
}) {
  const ok = runs.filter((r) => r.status === "ok");
  const data = checkpoints.flatMap((evals, k) => {
    const values = ok
      .map((r) => r.precision_trace[k])
      .filter((v): v is number => v != null)
      .sort((a, b) => a - b);
    if (values.length === 0) return [];
    const others = Object.fromEntries(overlays.map((o, i) => [`o${i}`, o.median[k] ?? undefined]));
    return [
      {
        evals,
        median: quantile(values, 0.5),
        band: [quantile(values, 0.25), quantile(values, 0.75)],
        ...others,
      },
    ];
  });
  if (data.length === 0) {
    return <p className="py-6 text-sm text-muted-foreground">No successful runs to plot.</p>;
  }

  const ticks = evalTicks(data[data.length - 1].evals);

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
              name="This submission (25th to 75th percentile)"
              legendType="none"
              stroke="none"
              fill="var(--foreground)"
              fillOpacity={0.15}
              isAnimationActive={false}
            />
            {overlays.map((o, i) => (
              <Line
                key={o.submission_id}
                dataKey={`o${i}`}
                name={o.is_baseline ? o.label : `${o.label} (best)`}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={1.5}
                strokeDasharray={o.is_baseline ? "5 4" : undefined}
                dot={false}
                isAnimationActive={false}
              />
            ))}
            {overlays.length > 0 && <Legend verticalAlign="top" height={32} iconType="plainline" />}
            <Line
              dataKey="median"
              name="This submission (median)"
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
        {ok.length === 1 ? "" : "s"}. Black line: median of this submission. Band: its 25th to
        75th percentile. Lower is better.
        {overlays.length > 0 &&
          " Coloured lines: median of the top entries (solid) and the baselines (dashed)."}
      </figcaption>
    </figure>
  );
}
