import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.describe("agent workflow is visible", () => {
  test("a reply in the agent panel shows which agents and tools handled it", async ({ page }) => {
    await signIn(page, "manager");
    const rail = page.getByRole("complementary", { name: "ORBIT agent" });
    if (!(await rail.isVisible())) await page.getByRole("button", { name: /Agent/ }).click();

    await rail.getByLabel("Message ORBIT").fill("show my overdue tasks");
    await rail.getByRole("button", { name: "Send message" }).click();

    // While it works the panel explains what is happening.
    await expect(rail.getByText(/Supervisor is reading your request/).or(rail.getByText("How ORBIT handled this"))).toBeVisible();

    const workflow = rail.getByRole("list", { name: "Agent workflow" }).last();
    await expect(workflow).toBeVisible({ timeout: 30_000 });
    await expect(workflow.getByText("Your request")).toBeVisible();
    await expect(workflow.getByText("show my overdue tasks")).toBeVisible();
    await expect(workflow.getByText("Supervisor")).toBeVisible();
    await expect(workflow.getByText(/Understood:/)).toBeVisible();
    await expect(workflow.getByText("Recommendation agent")).toBeVisible();
    await expect(workflow.getByRole("list", { name: "Tools used, in order" })).toContainText("Get overdue tasks");
    await expect(workflow.getByText("Replied")).toBeVisible();
    if (process.env.E2E_SCREENSHOTS) await page.screenshot({ path: "test-results/screens/agent-panel-workflow.png" });
  });

  test("the Agent workflow page explains the architecture and opens a run", async ({ page }) => {
    await signIn(page, "manager");
    await page.getByRole("navigation", { name: "Primary" }).first().getByRole("link", { name: "Agent workflow" }).click();
    await expect(page).toHaveURL(/\/traces/);
    await expect(page.getByRole("heading", { name: "Agent workflow", level: 1 }).first()).toBeVisible();

    const overview = page.getByText("How ORBIT works").first();
    await expect(overview).toBeVisible();
    for (const agent of ["Task agent", "Planner agent", "Recommendation agent", "Review agent"]) {
      await expect(page.getByRole("listitem").filter({ hasText: agent }).first()).toBeVisible();
    }

    // Make sure there is at least one run, then open it.
    const rail = page.getByRole("complementary", { name: "ORBIT agent" });
    if (!(await rail.isVisible())) await page.getByRole("button", { name: /Agent/ }).click();
    await rail.getByLabel("Message ORBIT").fill("help");
    await rail.getByRole("button", { name: "Send message" }).click();
    await expect(rail.getByRole("list", { name: "Agent workflow" }).last()).toBeVisible({ timeout: 30_000 });

    await page.reload();
    await page.getByRole("button", { name: "Show workflow" }).first().click();
    const diagram = page.getByRole("list", { name: "Agent workflow" }).first();
    await expect(diagram.getByText("Supervisor")).toBeVisible();
    await expect(diagram.getByText(/Decided by/)).toBeVisible();
    if (process.env.E2E_SCREENSHOTS) await page.screenshot({ path: "test-results/screens/agent-workflow-page.png", fullPage: true });
  });

  test("the admin screen shows whether Google Chat is connected", async ({ page }) => {
    await signIn(page, "manager");
    await page.goto("/admin");
    await expect(page.getByRole("tab", { name: "Integrations" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText("Google Chat").first()).toBeVisible();
    await expect(page.getByText("Request verification")).toBeVisible();
    await expect(page.getByText("Messages received, last 24 hours")).toBeVisible();
    await expect(page.getByText("AI model")).toBeVisible();
    if (process.env.E2E_SCREENSHOTS) await page.screenshot({ path: "test-results/screens/admin-integrations.png", fullPage: true });
  });

  test("employees cannot open the integrations status", async ({ page }) => {
    await signIn(page, "employee");
    await page.goto("/admin");
    await expect(page).toHaveURL("/");
  });
});
