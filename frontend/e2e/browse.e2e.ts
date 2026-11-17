import { expect, test } from "@playwright/test";

const PAGES: [string, string][] = [
  ["/problems", "Problems"],
  ["/leaderboard", "Leaderboard"],
  ["/statistics", "Statistics"],
  ["/contests", "Contests"],
  ["/research", "Research"],
  ["/login", "Sign in"],
];

test("public pages load without errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByRole("link", { name: "TopRanker" })).toBeVisible();
  for (const [path, title] of PAGES) {
    await page.goto(path);
    await expect(page.getByText(title, { exact: true }).first()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("pages that need an account send visitors to sign in", async ({ page }) => {
  await page.goto("/problems/STD-001");
  await expect(page.getByRole("link", { name: "Sign in" }).last()).toBeVisible();
  await page.goto("/admin");
  await expect(page.getByText("This page is for admins.")).toBeVisible();
});
