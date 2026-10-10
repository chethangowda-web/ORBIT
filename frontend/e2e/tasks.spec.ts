import { expect, test } from "@playwright/test";
import { apiCreateTask, apiDeleteTask, signIn, uniqueTitle } from "./helpers";

test.describe("tasks", () => {
  test("create from the board, advance it, then complete it from the detail page", async ({ page }) => {
    await signIn(page, "manager");
    const title = uniqueTitle("create");

    await page.getByRole("button", { name: "New task" }).first().click();
    const dialog = page.getByRole("dialog", { name: "New task" });
    await dialog.getByLabel("Title").fill(title);
    await dialog.getByRole("button", { name: "Create task" }).click();
    await expect(dialog).toBeHidden();

    await expect(page.getByRole("region", { name: /^To do lane/ }).getByText(title)).toBeVisible();

    await page.getByRole("button", { name: `Move "${title}" to In progress` }).click();
    await expect(page.getByRole("region", { name: /^In progress lane/ }).getByText(title)).toBeVisible();

    await page.getByRole("link", { name: title }).click();
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
    await page.getByRole("button", { name: "Mark done" }).click();
    await expect(page.getByText("Sarah Connor marked the task done")).toBeVisible();

    await apiDeleteTask(page, page.url().split("/").pop()!);
  });

  test("the form blocks an empty title", async ({ page }) => {
    await signIn(page, "employee");
    await page.getByRole("button", { name: "New task" }).first().click();
    const dialog = page.getByRole("dialog", { name: "New task" });
    await dialog.getByRole("button", { name: "Create task" }).click();
    await expect(dialog.getByText("A title is required.")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  });

  test("search and filters live in the URL and persist on reload", async ({ page }) => {
    await signIn(page, "manager");
    const title = uniqueTitle("findme");
    const id = await apiCreateTask(page, title);

    await page.goto("/tasks");
    await page.getByLabel("Search tasks").fill(title);
    await expect(page).toHaveURL(/q=findme/);
    await expect(page.getByRole("link", { name: title })).toBeVisible();

    await page.reload();
    await expect(page.getByLabel("Search tasks")).toHaveValue(title);
    await expect(page.getByRole("link", { name: title })).toBeVisible();

    await page.getByLabel("Status").selectOption("DONE");
    await expect(page.getByText("No tasks match these filters")).toBeVisible();
    await page.getByRole("button", { name: "Clear filters" }).click();

    await apiDeleteTask(page, id);
  });

  test("managers can delete after confirming; employees have no delete action", async ({ page }) => {
    await signIn(page, "manager");
    const title = uniqueTitle("delete");
    await apiCreateTask(page, title);
    await page.goto(`/tasks?q=${encodeURIComponent(title)}`);

    await page.getByRole("button", { name: `Delete "${title}"` }).click();
    const confirm = page.getByRole("dialog", { name: "Delete this task?" });
    await expect(confirm).toBeVisible();
    await confirm.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByRole("link", { name: title })).toBeVisible();

    await page.getByRole("button", { name: `Delete "${title}"` }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Delete task" }).click();
    await expect(page.getByRole("link", { name: title })).toHaveCount(0);

    await page.context().clearCookies();
    await page.evaluate(() => localStorage.clear());
    await signIn(page, "employee");
    await page.goto("/tasks");
    await expect(page.getByRole("button", { name: /^Delete "/ })).toHaveCount(0);
  });
});
