import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against a live stack (backend on :8001 with seeded data,
 * frontend on :3000). They do not start servers themselves:
 *   docker compose up -d postgres redis
 *   (backend/)  alembic upgrade head && python -m db.seed && uvicorn main:app --port 8001
 *   (frontend/) npm run build && npm start
 *   (frontend/) npm run test:e2e
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 8_000 },
  reporter: [["list"]],
  outputDir: "./test-results",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
