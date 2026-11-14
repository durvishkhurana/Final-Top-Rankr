import { expect, test } from "vitest";

import { fmtPrecision, fmtScore } from "./format";

test("precision is shown in scientific notation and floored at the scoring limit", () => {
  expect(fmtPrecision(0.000182)).toBe("1.82e-4");
  expect(fmtPrecision(1e-8)).toBe("≤ 1e-8");
  expect(fmtPrecision(null)).toBe("–");
});

test("scores are whole numbers, missing scores are a dash", () => {
  expect(fmtScore(208.6)).toBe("209");
  expect(fmtScore(null)).toBe("–");
  expect(fmtScore(0)).toBe("0");
});
