import { describe, expect, it } from "vitest";

import { Episode, yawDegrees } from "./integrity";

function rotationY(deg: number): number[] {
  const a = (deg * Math.PI) / 180;
  // column-major 4x4 rotation about the vertical axis
  return [Math.cos(a), 0, -Math.sin(a), 0, 0, 1, 0, 0, Math.sin(a), 0, Math.cos(a), 0, 0, 0, 0, 1];
}

describe("yawDegrees", () => {
  it("is zero facing the camera and the turn angle otherwise", () => {
    expect(yawDegrees(rotationY(0))).toBeCloseTo(0);
    expect(yawDegrees(rotationY(40))).toBeCloseTo(40);
    expect(yawDegrees(rotationY(-40))).toBeCloseTo(40);
  });
});

describe("Episode", () => {
  it("reports only episodes that last long enough", () => {
    const e = new Episode(3000);
    expect(e.update(true, 0)).toBeNull();
    expect(e.update(true, 1000)).toBeNull();
    expect(e.update(false, 2000)).toBeNull(); // too short
    expect(e.update(true, 5000)).toBeNull();
    expect(e.update(false, 9000)).toBe(4000);
    expect(e.update(false, 9500)).toBeNull();
  });

  it("can be closed at the end of the test", () => {
    const e = new Episode(1000);
    e.update(true, 0);
    expect(e.end(2500)).toBe(2500);
  });
});
