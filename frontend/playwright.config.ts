import { defineConfig, devices } from "@playwright/test";

/** Browser tests against a running stack (frontend, API, worker with the sandbox).
 *  docs/TESTING.md explains how to start one. */
export default defineConfig({
  testDir: "e2e",
  testMatch: "*.e2e.ts",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
