import { readFileSync } from "node:fs";

import { expect, type Page } from "@playwright/test";

export const PASSWORD = "e2e password 123";

/** Backend log, where emails are written when no SMTP server is configured. */
const API_LOG = process.env.E2E_API_LOG ?? "/tmp/topranker-api.log";

export const uniqueEmail = (name: string) => `${name}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;

/** The most recent emailed link to a page (verify-email or reset-password) for this address. */
export function emailedLink(email: string, page: "verify-email" | "reset-password"): string {
  const log = readFileSync(API_LOG, "utf8");
  const mails = log.split("SMTP is not configured; email to ").filter((m) => m.startsWith(email));
  const link = mails.at(-1)?.match(new RegExp(`https?://\\S+/${page}\\?token=\\S+`));
  if (!link) throw new Error(`No ${page} email for ${email} in ${API_LOG}`);
  return new URL(link[0]).pathname + new URL(link[0]).search;
}

/** Creates an account through the API; the page's browser context is then signed in. */
export async function signUp(page: Page, name: string): Promise<string> {
  const email = uniqueEmail(name.toLowerCase().replace(/\W+/g, "-"));
  const r = await page.request.post("/api/auth/signup", { data: { email, name, password: PASSWORD } });
  expect(r.status()).toBe(201);
  return email;
}

export async function signIn(page: Page, email: string, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Submits code through the API and waits until the worker has judged it. */
export async function judged(page: Page, problemId: string, dim: number, code: string): Promise<number> {
  const r = await page.request.post("/api/submissions", { data: { problem_id: problemId, dim, code } });
  expect(r.status()).toBe(201);
  const { id } = await r.json();
  await expect
    .poll(async () => (await (await page.request.get(`/api/submissions/${id}`)).json()).status, { timeout: 90_000 })
    .toBe("done");
  return id;
}
