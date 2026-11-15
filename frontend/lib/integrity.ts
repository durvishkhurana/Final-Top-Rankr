/** Head yaw in degrees from a MediaPipe facial transformation matrix (4x4, flattened).
 *  Only the size of the angle is used, so the storage order of the matrix does not matter:
 *  either order puts ±sin(yaw) at index 8 and cos(yaw) at index 10. */
export function yawDegrees(data: number[]): number {
  return Math.abs((Math.atan2(data[8], data[10]) * 180) / Math.PI);
}

/** Tracks a condition over time (no face, two faces, head turned). When an episode that
 *  lasted at least `minMs` ends, update() returns its duration; otherwise null. */
export class Episode {
  private start: number | null = null;
  constructor(private minMs: number) {}

  update(active: boolean, t: number): number | null {
    if (active) {
      this.start ??= t;
      return null;
    }
    return this.end(t);
  }

  end(t: number): number | null {
    if (this.start === null) return null;
    const ms = t - this.start;
    this.start = null;
    return ms >= this.minMs ? ms : null;
  }
}
