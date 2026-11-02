import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against a real PocketBase serving a release bundle.
// scripts/e2e.sh builds the bundle, starts it, and sets BRIEFER_URL.
export default defineConfig({
  testDir: "./e2e",
  timeout: 15_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.BRIEFER_URL ?? "http://127.0.0.1:8090",
    trace: "retain-on-failure",
  },
  projects: [{ name: "mobile-chromium", use: { ...devices["Pixel 7"] } }],
});
