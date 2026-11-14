import { defineConfig, devices } from "@playwright/test";

// Default: typed flow against the labelled fixture mock (no backend, no accounts).
// E2E_API_MODE=live runs the same suite against a running local API (separately reported).
const LIVE = process.env.E2E_API_MODE === "live";
const PORT = LIVE ? 3200 : 3100;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  // A live model-backed API answers each advance in seconds, not milliseconds.
  timeout: LIVE ? 180_000 : 30_000,
  expect: { timeout: LIVE ? 30_000 : 5_000 },
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone-390", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 } } },
  ],
  workers: process.env.CI ? 2 : undefined,
  webServer: {
    // Production build: NEXT_PUBLIC_* values are inlined at build time, so each run rebuilds.
    command: `npx next build && npx next start --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: {
      NEXT_PUBLIC_API_MODE: LIVE ? "live" : "mock",
      NEXT_PUBLIC_API_BASE_URL: process.env.E2E_API_BASE_URL ?? "http://localhost:8000",
      // Never use real provider credentials from .env.local in automated tests.
      // Next.js does not override variables already present in process.env.
      ELEVENLABS_API_KEY: "",
      ELEVENLABS_AGENT_ID: "",
    },
  },
});
