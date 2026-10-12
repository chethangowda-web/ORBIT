import { expect, test, type Page } from "@playwright/test";
import { API, signIn } from "./helpers";

/** Words that belong in code and logs, not on screen. */
const JARGON = /\b(supervisor|intents?|classif\w*|LLM|Gemini|PostgreSQL|Redis|webhooks?|JSON|UUID|cron|scheduler|payload|endpoints?|API|token|latency|SMTP|circuit|audience|service account|traces?|agents?|orchestrat\w*|pipeline|MultipleResultsFound)\b/i;

async function openAskOrbit(page: Page) {
  const rail = page.getByRole("complementary", { name: "Ask ORBIT" });
  if (!(await rail.isVisible())) await page.getByRole("button", { name: /Ask ORBIT/ }).click();
  await expect(rail).toBeVisible();
  return rail;
}

/** Titles, descriptions and tags are the team's own words, so they are not part of the check. */
async function userWrittenText(page: Page): Promise<string[]> {
  return page.evaluate(async (api) => {
    const token = localStorage.getItem("orbit_token");
    const res = await fetch(`${api}/tasks?page_size=100`, { headers: { Authorization: `Bearer ${token}` } });
    const rows = ((await res.json()).data ?? []) as { title?: string; description?: string; tags?: string[] }[];
    return rows.flatMap((t) => [t.title ?? "", t.description ?? "", ...(t.tags ?? []).map((tag) => `#${tag}`)]).filter(Boolean);
  }, API);
}

async function expectPlainLanguage(page: Page, where: string) {
  let text = await page.locator("body").innerText();
  for (const own of (await userWrittenText(page)).sort((a, b) => b.length - a.length)) text = text.split(own).join(" ");
  const found = text.match(JARGON);
  expect(found, `${where} shows the technical word "${found?.[0]}"`).toBeNull();
}

test.describe("ORBIT activity is visible, in everyday words", () => {
  test("Ask ORBIT is closed until opened, then shows how a request was handled", async ({ page }) => {
    await signIn(page, "manager");
    await expect(page.getByRole("complementary", { name: "Ask ORBIT" })).toHaveCount(0);

    const rail = await openAskOrbit(page);
    await rail.getByLabel("Message ORBIT").fill("show my overdue tasks");
    await rail.getByRole("button", { name: "Send message" }).click();

    await expect(rail.getByText(/Reading your request/).or(rail.getByText("How ORBIT handled this"))).toBeVisible();

    const handled = rail.getByRole("list", { name: "How this was handled" }).last();
    await expect(handled).toBeVisible({ timeout: 30_000 });
    await expect(handled.getByText("Your request")).toBeVisible();
    await expect(handled.getByText("show my overdue tasks")).toBeVisible();
    await expect(handled.getByText("Coordinator")).toBeVisible();
    await expect(handled.getByText(/Understood:/)).toBeVisible();
    await expect(handled.getByText("Advisor")).toBeVisible();
    await expect(handled.getByRole("list", { name: "What it did, in order" })).toContainText("Checked what is late");
    await expect(handled.getByText("Done", { exact: true })).toBeVisible();

    await expectPlainLanguage(page, "the Ask ORBIT panel");
    if (process.env.E2E_SCREENSHOTS) await page.screenshot({ path: "test-results/screens/agent-panel-workflow.png" });
  });

  test("the ORBIT activity page explains the team and opens a request", async ({ page }) => {
    await signIn(page, "manager");
    await page.getByRole("navigation", { name: "Primary" }).first().getByRole("link", { name: "ORBIT activity" }).click();
    await expect(page).toHaveURL(/\/traces/);
    await expect(page.getByRole("heading", { name: "ORBIT activity", level: 1 }).first()).toBeVisible();
    await expect(page.getByText("Your ORBIT team").first()).toBeVisible();
    for (const helper of ["Task helper", "Day planner", "Advisor", "Reviewer"]) {
      await expect(page.getByRole("listitem").filter({ hasText: helper }).first()).toBeVisible();
    }

    const rail = await openAskOrbit(page);
    await rail.getByLabel("Message ORBIT").fill("help");
    await rail.getByRole("button", { name: "Send message" }).click();
    await expect(rail.getByRole("list", { name: "How this was handled" }).last()).toBeVisible({ timeout: 30_000 });

    await page.reload();
    await page.getByRole("button", { name: "Show details" }).first().click();
    const diagram = page.getByRole("list", { name: "How this was handled" }).first();
    await expect(diagram.getByText("Coordinator")).toBeVisible();
    await expect(diagram.getByText(/Understood by/)).toBeVisible();

    await expectPlainLanguage(page, "the ORBIT activity page");
    if (process.env.E2E_SCREENSHOTS) await page.screenshot({ path: "test-results/screens/agent-workflow-page.png", fullPage: true });
  });

  test("the admin screens show connections and reminders without technical wording", async ({ page }) => {
    await signIn(page, "manager");
    await page.goto("/admin");
    await expect(page.getByRole("tab", { name: "Connections" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText("Google Chat").first()).toBeVisible();
    await expect(page.getByText("Only real Google messages are accepted")).toBeVisible();
    await expect(page.getByText("Messages in the last 24 hours")).toBeVisible();
    await expectPlainLanguage(page, "the Connections tab");
    if (process.env.E2E_SCREENSHOTS) await page.screenshot({ path: "test-results/screens/admin-integrations.png", fullPage: true });

    await page.getByRole("tab", { name: "Reminders" }).click();
    await expect(page.getByText("Automatic reminders")).toBeVisible();
    await expect(page.getByText("Every day at 9:00 am")).toBeVisible();
    await expectPlainLanguage(page, "the Reminders tab");

    await page.getByRole("tab", { name: "Notifications" }).click();
    await expect(page.getByText("Messages sent").first()).toBeVisible();
    await expectPlainLanguage(page, "the Notifications tab");
  });

  test("every main screen is free of technical words", async ({ page }) => {
    await signIn(page, "manager");
    for (const path of ["/", "/tasks", "/insights", "/profile"]) {
      await page.goto(path);
      await page.waitForLoadState("load");
      await page.waitForTimeout(800);
      await expectPlainLanguage(page, path);
    }
    await page.goto("/login");
  });

  test("employees cannot open the connections screen", async ({ page }) => {
    await signIn(page, "employee");
    await page.goto("/admin");
    await expect(page).toHaveURL("/");
  });
});
