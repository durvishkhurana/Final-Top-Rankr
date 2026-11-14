"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";

// Monaco needs the browser; it is loaded on demand.
const Monaco = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => <Skeleton className="h-full w-full" />,
});

export function CodeEditor({
  value,
  onChange,
  readOnly = false,
  height = 420,
}: {
  value: string;
  onChange?: (code: string) => void;
  readOnly?: boolean;
  height?: number;
}) {
  return (
    <div className="overflow-hidden rounded-lg border" style={{ height }}>
      <Monaco
        language="python"
        value={value}
        onChange={(v) => onChange?.(v ?? "")}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 13,
          scrollBeyondLastLine: false,
          tabSize: 4,
          ariaLabel: readOnly ? "Submitted code" : "Optimizer code editor",
        }}
      />
    </div>
  );
}
