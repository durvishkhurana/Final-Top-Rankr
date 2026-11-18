import { expect, test } from "@playwright/test";

import { emailedLink, PASSWORD, signIn, signUp, uniqueEmail } from "./helpers";

test("sign up, confirm the email address and reset the password", async ({ page }) => {
  const email = uniqueEmail("ada");
  await page.goto("/signup");
  await page.getByLabel("Name").fill("Ada");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password (at least 8 characters)").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/problems$/);
  const banner = page.getByText("Please confirm your email address");
  await expect(banner).toBeVisible();

  await page.goto(emailedLink(email, "verify-email"));
  await expect(page.getByText("your email address is confirmed")).toBeVisible();
  await expect(banner).toBeHidden();

  await page.getByRole("button", { name: "Sign out" }).click();
  await page.goto("/login");
  await page.getByRole("link", { name: "Forgot your password?" }).click();
  await expect(page.getByText("Reset your password")).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByText("a reset link is on its way")).toBeVisible();

  await page.goto(emailedLink(email, "reset-password"));
  await page.getByLabel(/New password/).fill("a different password");
  await page.getByRole("button", { name: "Set password" }).click();
  await expect(page.getByText("Your password has been changed")).toBeVisible();

  await signIn(page, email, PASSWORD);
  await expect(page.getByText("Wrong email or password")).toBeVisible();
  await signIn(page, email, "a different password");
  await expect(page).toHaveURL(/\/problems$/);
  await expect(page.getByRole("link", { name: "Ada" })).toBeVisible();
});

test("repeated wrong passwords lock sign-in", async ({ page }) => {
  const email = await signUp(page, "Bob");
  await page.context().clearCookies();
  for (let i = 0; i < 5; i++) {
    await signIn(page, email, "not the password");
    await expect(page.getByText("Wrong email or password")).toBeVisible();
  }
  await signIn(page, email);
  await expect(page.getByText("Too many failed sign-in attempts")).toBeVisible();
});
