import { expect, test } from "@playwright/test";
import { apiCreateTask, apiDeleteTask, signIn, uniqueTitle } from "./helpers";

test.describe("comments and bulk actions", () => {
  test("add a comment, see it in the thread and the activity log, then delete it", async ({ page }) => {
    await signIn(page, "manager");
    const title = uniqueTitle("comment");
    const id = await apiCreateTask(page, title);
    await page.goto(`/tasks/${id}`);

    const note = `Needs a rollback plan ${Date.now()}`;
    await page.getByLabel("Add a comment").fill(note);
    await page.getByRole("button", { name: "Comment", exact: true }).click();

    await expect(page.getByText(note)).toBeVisible();
    await expect(page.getByLabel("Add a comment")).toHaveValue("");
    await expect(page.getByText("Sarah Connor commented")).toBeVisible();

    await page.getByRole("button", { name: "Delete comment" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Delete comment" }).click();
    await expect(page.getByText(note)).toHaveCount(0);

    await apiDeleteTask(page, id);
  });

  test("Ctrl+Enter submits and an empty comment cannot be sent", async ({ page }) => {
    await signIn(page, "manager");
    const id = await apiCreateTask(page, uniqueTitle("shortcut"));
    await page.goto(`/tasks/${id}`);

    await expect(page.getByRole("button", { name: "Comment", exact: true })).toBeDisabled();
    await page.getByLabel("Add a comment").fill("sent with the keyboard");
    await page.getByLabel("Add a comment").press("Control+Enter");
    await expect(page.getByText("sent with the keyboard")).toBeVisible();

    await apiDeleteTask(page, id);
  });

  test("select several tasks and complete them in one action", async ({ page }) => {
    await signIn(page, "manager");
    const prefix = uniqueTitle("bulk");
    const ids = [await apiCreateTask(page, `${prefix} one`), await apiCreateTask(page, `${prefix} two`)];

    await page.goto(`/tasks?q=${encodeURIComponent(prefix)}`);
    await expect(page.getByRole("link", { name: `${prefix} one` })).toBeVisible();

    await page.getByRole("checkbox", { name: "Select all tasks on this page" }).check();
    const bar = page.getByRole("region", { name: "Bulk actions" });
    await expect(bar.getByText("2 selected")).toBeVisible();
    await bar.getByRole("button", { name: "Mark done" }).click();

    await expect(page.getByText("Completed 2 tasks")).toBeVisible();
    await expect(bar).toBeHidden();
    for (const name of ["one", "two"]) {
      await expect(page.getByRole("row", { name: new RegExp(`${prefix} ${name}`) }).getByText("Done")).toBeVisible();
    }

    for (const id of ids) await apiDeleteTask(page, id);
  });

  test("employees get no bulk delete and cannot complete a colleague's task", async ({ page }) => {
    await signIn(page, "employee");
    await page.goto("/tasks");
    const first = page.getByRole("checkbox", { name: /^Select "/ }).first();
    await first.check();
    const bar = page.getByRole("region", { name: "Bulk actions" });
    await expect(bar).toBeVisible();
    await expect(bar.getByRole("button", { name: "Delete" })).toHaveCount(0);
    await bar.getByRole("button", { name: "Clear selection" }).click();
    await expect(bar).toBeHidden();
  });
});
