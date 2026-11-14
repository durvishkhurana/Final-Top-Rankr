export const fmtPrecision = (p: number | null | undefined) =>
  p == null ? "–" : p <= 1e-8 ? "≤ 1e-8" : p.toExponential(2);

export const fmtScore = (s: number | null | undefined) => (s == null ? "–" : s.toFixed(0));

export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

export const fmtInt = (n: number) => n.toLocaleString();
