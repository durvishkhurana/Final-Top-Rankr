import { expect, test } from "@playwright/test";

import { signIn } from "./helpers";

const email = process.env.E2E_ADMIN_EMAIL;
const password = process.env.E2E_ADMIN_PASSWORD;

test.skip(!email || !password, "set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD to run the admin tests");

test("an admin starts an AI challenger and follows its generations", async ({ page }) => {
  await signIn(page, email!, password);
  await expect(page).toHaveURL(/\/problems$/);
  await page.goto("/admin");
  await page.getByRole("tab", { name: "AI challengers" }).click();
  await page.getByLabel("Problem", { exact: true }).selectOption("STD-002");
  await page.getByRole("button", { name: "Start", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: "STD-002" });
  await expect(row).toBeVisible();

  await row.getByRole("link").click();
  await page.getByRole("tab", { name: "Leaderboard" }).click();
  // with no AI provider configured the generation fails and says why; with one it is judged
  await expect(page.getByText("Generation 1")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByRole("heading", { name: "AI challenger" })).toBeVisible();
});

test("an admin queues the baselines on a problem", async ({ page }) => {
  await signIn(page, email!, password);
  await expect(page).toHaveURL(/\/problems$/);
  await page.goto("/admin");
  await page.getByRole("tab", { name: "Problems" }).click();
  await page.getByRole("row").filter({ hasText: "STD-005" }).getByRole("button", { name: "5" }).first().click();
  await expect(page.getByRole("status")).toContainText("Queued the three baselines on STD-005");
});
