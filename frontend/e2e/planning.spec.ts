import { expect, test, type Page } from "@playwright/test";
import { API, apiCreateTask, apiDeleteTask, signIn, uniqueTitle } from "./helpers";

async function myId(page: Page): Promise<string> {
  return page.evaluate(async (api) => {
    const token = localStorage.getItem("orbit_token");
    const res = await fetch(`${api}/users/me`, { headers: { Authorization: `Bearer ${token}` } });
    return (await res.json()).data.id as string;
  }, API);
}

async function createAssignedToMe(page: Page, title: string, dueInDays: number): Promise<string> {
  const me = await myId(page);
  const due = new Date(Date.now() + dueInDays * 86_400_000).toISOString().slice(0, 10);
  return page.evaluate(
    async ({ api, taskTitle, assignee, dueDate }) => {
      const token = localStorage.getItem("orbit_token");
      const res = await fetch(`${api}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ title: taskTitle, priority: "HIGH", assignee_id: assignee, due_date: dueDate }),
      });
      return (await res.json()).data.id as string;
    },
    { api: API, taskTitle: title, assignee: me, dueDate: due },
  );
}

test.describe("planning and smart help", () => {
  test("the new-task form warns about a task that already exists", async ({ page }) => {
    await signIn(page, "manager");
    const title = uniqueTitle("Renew the annual licence");
    const id = await apiCreateTask(page, title);

    await page.getByRole("button", { name: "New task" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Title").fill(title);

    const warning = dialog.getByRole("status", { name: "Similar tasks" });
    await expect(warning).toContainText("This task already exists");
    await expect(warning).toContainText(title);
    await expect(dialog.getByRole("button", { name: "Create anyway" })).toBeVisible();
    if (process.env.E2E_SCREENSHOTS) await page.screenshot({ path: "test-results/screens/form-duplicate.png" });

    // A genuinely different title clears the warning and the button goes back to normal.
    await dialog.getByLabel("Title").fill("Order new office chairs for the team");
    await expect(warning).toHaveCount(0);
    await expect(dialog.getByRole("button", { name: "Create task" })).toBeVisible();

    await dialog.getByRole("button", { name: "Cancel" }).click();
    await apiDeleteTask(page, id);
  });

  test("a manager can see who has room and pick them", async ({ page }) => {
    await signIn(page, "manager");
    await page.getByRole("button", { name: "New task" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Who has room?" }).click();

    const options = dialog.getByRole("group", { name: "People with room" }).getByRole("button");
    await expect(options.first()).toBeVisible();
    await expect(options.first()).toContainText(/open tasks?|no open tasks/);
    await options.first().click();
    await expect(dialog.getByLabel("Assignee")).not.toHaveValue("");
    await dialog.getByRole("button", { name: "Cancel" }).click();
  });

  test("employees do not get the suggestion button", async ({ page }) => {
    await signIn(page, "employee");
    await page.getByRole("button", { name: "New task" }).first().click();
    await expect(page.getByRole("dialog").getByRole("button", { name: "Who has room?" })).toHaveCount(0);
  });

  test("My week lays out my tasks, late work first, and Ask ORBIT plans it too", async ({ page }) => {
    await signIn(page, "manager");
    const soon = uniqueTitle("Prepare the board pack");
    const late = uniqueTitle("Send the overdue report");
    const soonId = await createAssignedToMe(page, soon, 2);
    const lateId = await createAssignedToMe(page, late, -3);

    await page.getByRole("navigation", { name: "Primary" }).first().getByRole("link", { name: "My week" }).click();
    await expect(page).toHaveURL(/\/week/);
    await expect(page.getByRole("heading", { name: "My week", level: 1 }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: soon })).toBeVisible();
    await expect(page.getByRole("link", { name: late })).toBeVisible();
    await expect(page.getByText(/3 days late/).first()).toBeVisible();
    if (process.env.E2E_SCREENSHOTS) await page.screenshot({ path: "test-results/screens/my-week.png", fullPage: true });

    // The late task sits on the first day, ahead of anything else.
    const firstDay = page.locator("ul").filter({ has: page.getByRole("link", { name: late }) }).first();
    await expect(firstDay.getByRole("link").first()).toHaveText(late);

    // The same plan from Ask ORBIT, in words.
    const rail = page.getByRole("complementary", { name: "Ask ORBIT" });
    if (!(await rail.isVisible())) await page.getByRole("button", { name: /Ask ORBIT/ }).click();
    await rail.getByLabel("Message ORBIT").fill("plan my week");
    await rail.getByRole("button", { name: "Send message" }).click();
    await expect(rail.getByText(/Your week/).first()).toBeVisible({ timeout: 30_000 });
    await expect(rail.getByText(soon).first()).toBeVisible();

    await apiDeleteTask(page, soonId);
    await apiDeleteTask(page, lateId);
  });
});
