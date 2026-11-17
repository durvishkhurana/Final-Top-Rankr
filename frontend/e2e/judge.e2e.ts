import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { judged, signUp } from "./helpers";

const CMAES = readFileSync("../backend/judge/baselines/cmaes.py", "utf8");

test("submit from the problem page, see the judged runs, compare and download", async ({ page, browser }) => {
  const run = Date.now().toString(36);
  const [ada, bobName] = [`Ada ${run}`, `Bob ${run}`];
  await signUp(page, ada);
  await page.goto("/problems/STD-001");
  await expect(page.getByRole("heading", { name: "Sphere" })).toBeVisible();
  await page.getByRole("button", { name: "Submit at dimension 5" }).click();

  await expect(page).toHaveURL(/\/submissions\/\d+$/);
  await expect(page.getByText("Score", { exact: true })).toBeVisible({ timeout: 90_000 });
  await expect(page.getByRole("heading", { name: "Convergence" })).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(16); // header and 15 runs
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "CSV" }).click();
  expect((await download).suggestedFilename()).toMatch(/^submission-\d+-runs\.csv$/);

  // a second participant with a stronger optimizer
  const bob = await browser.newPage();
  await signUp(bob, bobName);
  await judged(bob, "STD-001", 5, CMAES);
  await bob.close();

  await page.goto("/problems/STD-001");
  await page.getByRole("tab", { name: "Leaderboard" }).click();
  const rank = async (name: string) =>
    Number(await page.getByRole("row").filter({ hasText: name }).getByRole("cell").first().textContent());
  await expect(page.getByRole("row").filter({ hasText: bobName })).toBeVisible();
  expect(await rank(bobName)).toBeLessThan(await rank(ada));

  await page.getByRole("link", { name: "Compare entries statistically" }).click();
  await expect(page).toHaveURL(/\/research\?problem=STD-001&dim=5/);
  const ticked = page.getByRole("checkbox", { checked: true });
  while ((await ticked.count()) > 0) await ticked.first().uncheck();
  await page.getByRole("checkbox", { name: ada }).check();
  await page.getByRole("checkbox", { name: bobName }).check();
  await page.getByRole("button", { name: "Compare 2 entries" }).click();
  await expect(page.getByRole("heading", { name: "Pairwise tests" })).toBeVisible();
  await expect(page.getByText(`${bobName} is better`)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Runtime distribution (ECDF)" })).toBeVisible();
});
