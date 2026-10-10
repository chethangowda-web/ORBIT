import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.describe("app shell", () => {
  test("command palette opens with Ctrl+K, filters, and navigates with the keyboard", async ({ page }) => {
    await signIn(page, "manager");
    await page.keyboard.press("Control+k");
    const palette = page.getByRole("dialog", { name: "Command palette" });
    await expect(palette).toBeVisible();

    await palette.getByRole("combobox").fill("insights");
    await expect(palette.getByRole("option", { name: /Go to Insights/ })).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/insights/);
    await expect(palette).toBeHidden();
  });

  test("Escape closes the palette", async ({ page }) => {
    await signIn(page, "employee");
    await page.keyboard.press("Control+k");
    await expect(page.getByRole("dialog", { name: "Command palette" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Command palette" })).toBeHidden();
  });

  test("the agent panel answers and records a run", async ({ page }) => {
    await signIn(page, "employee");
    const rail = page.getByRole("complementary", { name: "ORBIT agent" });
    if (!(await rail.isVisible())) await page.getByRole("button", { name: /Agent/ }).click();
    await expect(rail).toBeVisible();

    await rail.getByLabel("Message ORBIT").fill("help");
    await rail.getByRole("button", { name: "Send message" }).click();
    await expect(rail.getByText(/ORBIT AI Task Assistant/)).toBeVisible();

    await rail.getByRole("tab", { name: "runs" }).click();
    await expect(rail.getByText("HELP").first()).toBeVisible();
  });

  test("the health indicator reflects a reachable API", async ({ page }) => {
    await signIn(page, "employee");
    await expect(page.getByRole("status").filter({ hasText: /All systems normal|Cache offline|Live/ })).toBeVisible();
  });

  test("the profile page saves a preference", async ({ page }) => {
    await signIn(page, "employee");
    await page.goto("/profile");
    const toggle = page.getByRole("switch", { name: /Morning briefing/ });
    const before = await toggle.isChecked();

    // Wait for the save to finish before reloading, otherwise the reload aborts it.
    const saved = () => page.waitForResponse((r) => r.url().includes("/users/me/preferences") && r.request().method() === "PATCH");
    await Promise.all([saved(), toggle.setChecked(!before, { force: true })]);

    await page.reload();
    await expect(page.getByRole("switch", { name: /Morning briefing/ })).toBeChecked({ checked: !before });

    await Promise.all([saved(), page.getByRole("switch", { name: /Morning briefing/ }).setChecked(before, { force: true })]);
  });
});
