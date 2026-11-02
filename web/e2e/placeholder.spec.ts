import { expect, test } from "@playwright/test";

test("serves the app with an environment banner that matches the live build", async ({ page, request }) => {
  const version = await (await request.get("/api/briefer/version")).json();
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Briefer" })).toBeVisible();
  await expect(page.getByRole("status")).toHaveText(`${version.env.toUpperCase()} · ${version.build}`);
  await expect(page).toHaveTitle(`[${version.env}] Briefer`);
});

test("falls back to index.html for client-side routes", async ({ page }) => {
  const res = await page.goto("/history");
  expect(res?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Briefer" })).toBeVisible();
});
