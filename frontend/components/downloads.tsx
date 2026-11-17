/** Links to an export endpoint in both formats. path is under /api and may carry a query. */
export function Downloads({ path, label = "Download" }: { path: string; label?: string }) {
  const sep = path.includes("?") ? "&" : "?";
  return (
    <span className="text-sm text-muted-foreground">
      {label}{" "}
      {(["csv", "json"] as const).map((f, i) => (
        <span key={f}>
          {i > 0 && " · "}
          <a href={`/api${path}${sep}format=${f}`} download className="text-foreground underline">
            {f.toUpperCase()}
          </a>
        </span>
      ))}
    </span>
  );
}
