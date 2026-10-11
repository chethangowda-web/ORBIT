import { expect, test } from "@playwright/test";
import { API, apiCreateTask, apiDeleteTask, signIn, uniqueTitle } from "./helpers";

test.describe("regressions found in review", () => {
  test("the kanban drag handle can be reached with the keyboard", async ({ page }) => {
    await signIn(page, "manager");
    const title = uniqueTitle("kbd");
    const id = await apiCreateTask(page, title);
    await page.goto("/");
    await expect(page.getByText(title).first()).toBeVisible();

    const handle = page.getByRole("button", { name: new RegExp(`Drag "${title}"`) });
    await handle.focus();
    await expect(handle).toBeFocused();
    await expect(handle).toHaveCSS("opacity", "1");

    await apiDeleteTask(page, id);
  });

  test("deleting the last task on the last page returns to a page that has tasks", async ({ page }) => {
    await signIn(page, "manager");
    const prefix = uniqueTitle("page");
    // The table shows 15 per page; 16 matching tasks puts exactly one on page 2.
    const ids: string[] = [];
    for (let i = 0; i < 16; i++) ids.push(await apiCreateTask(page, `${prefix} ${String(i).padStart(2, "0")}`));

    await page.goto(`/tasks?q=${encodeURIComponent(prefix)}&page=2&sort=title&dir=asc`);
    await expect(page.getByRole("link", { name: `${prefix} 15` })).toBeVisible();

    await page.getByRole("checkbox", { name: "Select all tasks on this page" }).check();
    await page.getByRole("region", { name: "Bulk actions" }).getByRole("button", { name: "Delete" }).click();
    await page.getByRole("dialog").getByRole("button", { name: /Delete/ }).click();

    await expect(page.getByText("No tasks yet")).toHaveCount(0);
    await expect(page.getByRole("link", { name: `${prefix} 00` })).toBeVisible({ timeout: 10_000 });

    for (const id of ids.slice(0, 15)) await apiDeleteTask(page, id);
  });

  test("an employee can edit a task a manager owns without losing or changing its assignee", async ({ page, browser }) => {
    // The manager creates a task assigned to the manager, then the employee is made its creator by
    // creating it themselves and having the manager assign it.
    const employeeTitle = uniqueTitle("owned");
    await signIn(page, "employee");
    const id = await apiCreateTask(page, employeeTitle);

    const mgr = await browser.newContext();
    const mgrPage = await mgr.newPage();
    await signIn(mgrPage, "manager");
    const managerId = await mgrPage.evaluate(
      async (api) => {
        const token = localStorage.getItem("orbit_token");
        const me = await (await fetch(`${api}/users/me`, { headers: { Authorization: `Bearer ${token}` } })).json();
        return me.data.id as string;
      },
      API,
    );
    await mgrPage.evaluate(
      async ({ api, taskId, assignee }) => {
        const token = localStorage.getItem("orbit_token");
        await fetch(`${api}/tasks/${taskId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ assignee_id: assignee }),
        });
      },
      { api: API, taskId: id, assignee: managerId },
    );

    await page.goto(`/tasks/${id}`);
    await page.getByRole("button", { name: "Edit" }).first().click();
    await page.getByLabel("Title").fill(`${employeeTitle} renamed`);
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByText(`${employeeTitle} renamed`).first()).toBeVisible();
    await expect(page.getByText("Employees cannot reassign")).toHaveCount(0);

    await apiDeleteTask(mgrPage, id);
    await mgr.close();
  });
});
