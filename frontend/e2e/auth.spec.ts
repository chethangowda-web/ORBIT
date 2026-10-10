import { expect, test } from "@playwright/test";
import { ACCOUNTS, signIn } from "./helpers";

test.describe("authentication and access", () => {
  test("anonymous visitors are sent to the login page", async ({ page }) => {
    await page.goto("/tasks");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  });

  test("a wrong password shows an error and stays on the page", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Work email").fill(ACCOUNTS.employee.email);
    await page.getByLabel("Password").fill("definitely-wrong");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: /invalid email or password/i })).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("employees do not see manager screens and are redirected away from them", async ({ page }) => {
    await signIn(page, "employee");
    const nav = page.getByRole("navigation", { name: "Primary" }).first();
    await expect(nav.getByRole("link", { name: "Tasks" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Insights" })).toHaveCount(0);
    await expect(nav.getByRole("link", { name: "Admin" })).toHaveCount(0);

    await page.goto("/insights");
    await expect(page).toHaveURL("/");
    await page.goto("/admin");
    await expect(page).toHaveURL("/");
  });

  test("managers see Insights and Admin", async ({ page }) => {
    await signIn(page, "manager");
    const nav = page.getByRole("navigation", { name: "Primary" }).first();
    await expect(nav.getByRole("link", { name: "Insights" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Admin" })).toBeVisible();
    await page.goto("/insights");
    await expect(page.getByRole("heading", { name: "Insights", level: 1 }).first()).toBeVisible();
  });

  test("signing out ends the session", async ({ page }) => {
    await signIn(page, "employee");
    await page.getByRole("button", { name: "Account menu" }).click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/);
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });
});
