"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { ProblemView } from "@/lib/types";

const SIZE = 440;
const TRAIL = 120; // most recent points drawn in full colour

/** Dark = close to the optimum. Precision is mapped on a log scale. */
function shade(precision: number, lo: number, hi: number): [number, number, number] {
  const t = (Math.log10(precision + 1e-9) - lo) / (hi - lo || 1); // 0 near optimum, 1 far
  return [32 + 208 * t, 64 + 180 * t, 120 + 128 * t];
}

/** Contour-style map of a 2D demo landscape with the evaluated points of one run
 *  replayed in order. Without points it just shows the landscape. */
export function LandscapePlayer({ view, points }: { view: ProblemView; points?: [number, number][] }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const background = useRef<ImageBitmap | HTMLCanvasElement | null>(null);
  const total = points?.length ?? 0;
  const [shown, setShown] = useState(total);
  const [playing, setPlaying] = useState(false);

  // paint the landscape once per view
  useEffect(() => {
    const grid = view.grid;
    if (!grid) return;
    const n = grid.length;
    const logs = grid.flat().map((v) => Math.log10(v + 1e-9));
    const lo = Math.min(...logs);
    const hi = Math.max(...logs);
    const off = document.createElement("canvas");
    off.width = off.height = n;
    const ctx = off.getContext("2d")!;
    const image = ctx.createImageData(n, n);
    for (let row = 0; row < n; row++) {
      for (let col = 0; col < n; col++) {
        const [r, g, b] = shade(grid[row][col], lo, hi);
        const i = ((n - 1 - row) * n + col) * 4; // y grows upwards
        image.data.set([r, g, b, 255], i);
      }
    }
    ctx.putImageData(image, 0, 0);
    background.current = off;
  }, [view]);

  // draw the current frame
  useEffect(() => {
    const ctx = canvas.current?.getContext("2d");
    if (!ctx || !background.current) return;
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(background.current, 0, 0, SIZE, SIZE);
    if (!points) return;
    const sx = (x: number) => ((x - view.lower[0]) / (view.upper[0] - view.lower[0])) * SIZE;
    const sy = (y: number) => SIZE - ((y - view.lower[1]) / (view.upper[1] - view.lower[1])) * SIZE;
    for (let i = 0; i < shown; i++) {
      const recent = i >= shown - TRAIL;
      ctx.fillStyle = recent ? "rgba(255, 196, 0, 0.95)" : "rgba(255, 255, 255, 0.35)";
      ctx.beginPath();
      ctx.arc(sx(points[i][0]), sy(points[i][1]), recent ? 2.6 : 1.4, 0, 2 * Math.PI);
      ctx.fill();
    }
  }, [view, points, shown]);

  // advance while playing, about 6 seconds for a whole run
  useEffect(() => {
    if (!playing) return;
    let frame = requestAnimationFrame(function tick() {
      setShown((s) => {
        const next = Math.min(total, s + Math.max(1, Math.round(total / 360)));
        if (next >= total) setPlaying(false);
        return next;
      });
      frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  }, [playing, total]);

  if (!view.grid) return null;
  return (
    <figure className="max-w-full">
      <canvas
        ref={canvas}
        width={SIZE}
        height={SIZE}
        className="h-auto max-w-full rounded-lg border"
        role="img"
        aria-label={
          points
            ? `Landscape with ${shown} of ${total} sampled points of this run`
            : "Landscape of this problem instance"
        }
      />
      {points && (
        <div className="mt-2 flex max-w-[440px] items-center gap-3">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              if (!playing && shown >= total) setShown(0);
              setPlaying(!playing);
            }}
          >
            {playing ? "Pause" : shown >= total ? "Replay" : "Play"}
          </Button>
          <input
            type="range"
            min={0}
            max={total}
            value={shown}
            onChange={(e) => {
              setPlaying(false);
              setShown(Number(e.target.value));
            }}
            className="flex-1"
            aria-label="Position in the run"
          />
          <span className="w-24 text-right text-xs tabular-nums text-muted-foreground">
            {shown} / {total}
          </span>
        </div>
      )}
      <figcaption className="mt-1 max-w-[440px] text-xs text-muted-foreground">
        Darker means closer to the optimum (log scale).
        {points &&
          " Dots are an evenly thinned sample of the points this run evaluated, in order; the newest are yellow."}
      </figcaption>
    </figure>
  );
}
