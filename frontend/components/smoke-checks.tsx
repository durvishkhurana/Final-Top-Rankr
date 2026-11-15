import type { Contribution } from "@/lib/types";

/** Result of the sandboxed smoke test of a contributed function. */
export function SmokeChecks({ item }: { item: Contribution }) {
  if (!item.smoke) return <p className="text-sm text-muted-foreground">Smoke test running…</p>;
  return (
    <ul className="space-y-1 text-sm">
      {item.smoke.checks.map((c) => (
        <li key={c.name}>
          <span aria-hidden>{c.ok ? "✓" : "✗"}</span> {c.name}
          {!c.ok && c.detail && <span className="text-muted-foreground"> — {c.detail}</span>}
        </li>
      ))}
    </ul>
  );
}

export const STATUS_TEXT: Record<string, string> = {
  testing: "smoke test running",
  failed: "failed the smoke test",
  pending: "waiting for review",
  approved: "approved",
  rejected: "rejected",
};
