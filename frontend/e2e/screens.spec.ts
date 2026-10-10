import { expect, test } from "@playwright/test";
import { signIn, type Who } from "./helpers";

/**
 * Visual review helper: captures every screen into test-results/screens.
 * Skipped unless E2E_SCREENSHOTS=1 so normal runs stay fast.
 *   E2E_SCREENSHOTS=1 npx playwright test e2e/screens.spec.ts
 */
test.skip(process.env.E2E_SCREENSHOTS !== "1", "set E2E_SCREENSHOTS=1 to capture screenshots");

const SHOTS: { who: Who; path: string; name: string; wait?: string }[] = [
  { who: "manager", path: "/", name: "board" },
  { who: "manager", path: "/tasks", name: "tasks" },
  { who: "manager", path: "/insights", name: "insights" },
  { who: "manager", path: "/traces", name: "traces" },
  { who: "manager", path: "/admin", name: "admin-scheduler" },
  { who: "manager", path: "/admin?tab=notifications", name: "admin-notifications" },
  { who: "admin", path: "/admin?tab=users", name: "admin-users" },
  { who: "employee", path: "/profile", name: "profile" },
  { who: "employee", path: "/", name: "board-employee" },
];

test("login screen", async ({ page }) => {
  await page.goto("/login");
  await page.screenshot({ path: "test-results/screens/login.png" });
});

for (const shot of SHOTS) {
  test(`screen: ${shot.name}`, async ({ page }) => {
    await signIn(page, shot.who);
    await page.goto(shot.path);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `test-results/screens/${shot.name}.png` });
  });
}

test("command palette and mobile layout", async ({ page }) => {
  await signIn(page, "manager");
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox").fill("task");
  await page.waitForTimeout(500);
  await page.screenshot({ path: "test-results/screens/palette.png" });
  await page.keyboard.press("Escape");

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: "test-results/screens/mobile-board.png" });
});

test("task detail with comments and bulk selection", async ({ page }) => {
  const { apiCreateTask, apiDeleteTask, uniqueTitle } = await import("./helpers");
  await signIn(page, "manager");
  const title = uniqueTitle("Review release notes");
  const id = await apiCreateTask(page, title);
  const other = await apiCreateTask(page, uniqueTitle("Update runbook"));

  await page.goto(`/tasks/${id}`);
  for (const text of ["Draft is ready for review.", "Please double check the migration notes before we ship."]) {
    await page.getByLabel("Add a comment").fill(text);
    await page.getByRole("button", { name: "Comment", exact: true }).click();
    await expect(page.getByLabel("Add a comment")).toHaveValue(""); // saved and the composer reset
  }
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: "test-results/screens/task-detail.png", fullPage: true });

  await page.goto("/tasks");
  await page.getByRole("checkbox", { name: /^Select "/ }).nth(0).check();
  await page.getByRole("checkbox", { name: /^Select "/ }).nth(1).check();
  await page.screenshot({ path: "test-results/screens/bulk-selection.png" });

  await apiDeleteTask(page, id);
  await apiDeleteTask(page, other);
});
