import type { InstanceData, Problem, Solution } from "@/lib/types";

// colour-blind-safe set (Okabe-Ito)
export const PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000"];
const colour = (i: number) => PALETTE[i % PALETTE.length];

function MapFrame({ size, label, children }: { size: number; label: string; children: React.ReactNode }) {
  return (
    <svg
      viewBox={`-0.4 -0.4 ${size + 0.8} ${size + 0.8}`}
      className="aspect-square w-full max-w-md rounded-lg border bg-muted/30"
      role="img"
      aria-label={label}
    >
      {/* y grows upwards on the map */}
      <g transform={`translate(0 ${size}) scale(1 -1)`}>{children}</g>
    </svg>
  );
}

function Timetable({ data, solution }: { data: InstanceData; solution?: Solution }) {
  if (!solution?.slots) {
    return (
      <p className="text-sm">
        {data.courses?.length} courses with {data.courses?.reduce((a, c) => a + c.students, 0)}{" "}
        enrolments in total, {data.slots} slots, {data.rooms?.length} rooms per slot (capacities{" "}
        {data.rooms?.join(", ")}), {data.clash_pairs} pairs of courses share at least one student.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      <p className="text-sm">
        {solution.clashing_students} student clashes, {solution.unseated_students} students
        without a seat.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="border p-2 text-left">Slot</th>
              {data.rooms?.map((cap, r) => (
                <th key={r} className="border p-2 text-left">
                  Room {r + 1} <span className="font-normal text-muted-foreground">({cap} seats)</span>
                </th>
              ))}
              <th className="border p-2 text-left">No room</th>
            </tr>
          </thead>
          <tbody>
            {solution.slots.map((slot, s) => (
              <tr key={s}>
                <th className="border p-2 text-left font-medium">{s + 1}</th>
                {data.rooms?.map((_, r) => {
                  const exam = slot.find((e) => e.room === r + 1);
                  const over = exam && exam.students > exam.capacity;
                  return (
                    <td key={r} className={`border p-2 ${over ? "bg-destructive/10" : ""}`}>
                      {exam ? `${exam.course} (${exam.students})` : ""}
                      {over && <span className="text-destructive"> over capacity</span>}
                    </td>
                  );
                })}
                <td className="border p-2 text-destructive">
                  {slot
                    .filter((e) => e.room === null)
                    .map((e) => `${e.course} (${e.students})`)
                    .join(", ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Facility({ data, solution }: { data: InstanceData; solution?: Solution }) {
  const size = data.size ?? 10;
  return (
    <div className="space-y-2">
      <p className="text-sm">
        {solution?.mean_distance != null
          ? `Average walk to the nearest stop: ${solution.mean_distance.toFixed(3)} map units.`
          : `${data.demand?.length} demand points, ${data.stops} stops to place.`}{" "}
        Circle area shows how many people live at a point.
      </p>
      <MapFrame size={size} label="Map of demand points and stops">
        {data.demand?.map((p, i) => {
          const k = solution?.assigned?.[i];
          const stop = k != null ? solution?.stops?.[k] : undefined;
          return (
            <g key={i}>
              {stop && (
                <line x1={p.x} y1={p.y} x2={stop.x} y2={stop.y} stroke={colour(k!)} strokeWidth={0.03} opacity={0.6} />
              )}
              <circle cx={p.x} cy={p.y} r={0.05 + Math.sqrt(p.people) * 0.025}
                fill={k != null ? colour(k) : "currentColor"} opacity={0.75} />
            </g>
          );
        })}
        {solution?.stops?.map((s, k) => (
          <rect key={k} x={s.x - 0.17} y={s.y - 0.17} width={0.34} height={0.34}
            fill={colour(k)} stroke="white" strokeWidth={0.06} />
        ))}
      </MapFrame>
      {solution && <p className="text-xs text-muted-foreground">Squares are stops; each point is coloured by its nearest stop.</p>}
    </div>
  );
}

function Routing({ data, solution }: { data: InstanceData; solution?: Solution }) {
  const size = data.size ?? 10;
  const customers = data.customers ?? [];
  const depot = data.depot ?? { x: size / 2, y: size / 2 };
  return (
    <div className="space-y-2">
      <p className="text-sm">
        {solution?.total_distance != null
          ? `${solution.routes?.length} routes, ${solution.total_distance.toFixed(2)} map units driven in total.`
          : `${customers.length} customers, vehicle capacity ${data.capacity}.`}
      </p>
      <MapFrame size={size} label="Map of the depot, customers and routes">
        {solution?.routes?.map((route, r) => (
          <polyline
            key={r}
            fill="none"
            stroke={colour(r)}
            strokeWidth={0.06}
            points={[depot, ...route.customers.map((c) => customers[c]), depot]
              .map((p) => `${p.x},${p.y}`)
              .join(" ")}
          />
        ))}
        {customers.map((c, i) => (
          <circle key={i} cx={c.x} cy={c.y} r={0.08 + c.demand * 0.012} fill="currentColor" />
        ))}
        <rect x={depot.x - 0.2} y={depot.y - 0.2} width={0.4} height={0.4} fill="currentColor"
          stroke="white" strokeWidth={0.06} />
      </MapFrame>
      {solution?.routes && (
        <ul className="text-xs text-muted-foreground">
          {solution.routes.map((route, r) => (
            <li key={r}>
              <span style={{ color: colour(r) }}>■</span> Route {r + 1}: {route.customers.length}{" "}
              stops, load {route.load} of {data.capacity}
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted-foreground">The square is the depot; larger dots need larger deliveries.</p>
    </div>
  );
}

/** Instance data of a real-world problem, with the decoded solution of a run on top
 *  when one is given. */
export function SolutionView({
  kind,
  data,
  solution,
}: {
  kind: Problem["kind"];
  data: InstanceData;
  solution?: Solution;
}) {
  if (kind === "timetable") return <Timetable data={data} solution={solution} />;
  if (kind === "facility") return <Facility data={data} solution={solution} />;
  if (kind === "routing") return <Routing data={data} solution={solution} />;
  return null;
}
