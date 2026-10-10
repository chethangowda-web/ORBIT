import { expect, test } from "@playwright/test";
import { apiCreateTask, apiDeleteTask, signIn, uniqueTitle, API } from "./helpers";

test.describe("attachments", () => {
  test("attach, download and remove a file; unsafe types are refused", async ({ page }) => {
    await signIn(page, "manager");
    const id = await apiCreateTask(page, uniqueTitle("files"));
    await page.goto(`/tasks/${id}`);

    await page.getByLabel("Choose files to attach").setInputFiles({
      name: "release-notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("v2 ships on Friday"),
    });
    await expect(page.getByText("release-notes.txt").first()).toBeVisible();
    await expect(page.getByText("Sarah Connor attached release-notes.txt")).toBeVisible();

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Download release-notes.txt" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("release-notes.txt");

    // The browser-side check rejects an unsafe type before anything is sent.
    await page.getByLabel("Choose files to attach").setInputFiles({
      name: "payload.html",
      mimeType: "text/html",
      buffer: Buffer.from("<script>alert(1)</script>"),
    });
    await expect(page.getByText(/"payload.html" is not an allowed file type/)).toBeVisible();
    await expect(page.getByText("payload.html")).toHaveCount(1); // only inside the toast

    await page.getByRole("button", { name: "Remove release-notes.txt" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Remove file" }).click();
    await expect(page.getByRole("button", { name: "Download release-notes.txt" })).toHaveCount(0);

    await apiDeleteTask(page, id);
  });
});

test.describe("theme", () => {
  test("light theme applies, persists across reloads, and renders without a flash", async ({ page }) => {
    await signIn(page, "manager");
    const darkBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);

    await page.goto("/profile");
    await page.getByRole("radio", { name: "Light" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    const lightBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(lightBg).not.toBe(darkBg);

    // The server reads the cookie, so the very first HTML already carries the theme.
    const html = await (await page.request.get("/login")).text();
    expect(html).toContain('data-theme="light"');

    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await expect(page.getByRole("radio", { name: "Light" })).toHaveAttribute("aria-checked", "true");

    // Charts and every screen follow the tokens: visit insights and make sure it still renders.
    await page.goto("/insights");
    await expect(page.getByRole("heading", { name: "Insights", level: 1 }).first()).toBeVisible();

    await page.goto("/profile");
    await page.getByRole("radio", { name: "Dark" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  });

  test("system follows the operating system preference", async ({ page }) => {
    await signIn(page, "manager");
    await page.goto("/profile");
    await page.getByRole("radio", { name: "System" }).click();

    await page.emulateMedia({ colorScheme: "light" });
    const light = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    await page.emulateMedia({ colorScheme: "dark" });
    const dark = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(light).not.toBe(dark);

    await page.getByRole("radio", { name: "Dark" }).click();
  });
});

test.describe("live updates", () => {
  test("a change made elsewhere appears without reloading or waiting for the poll", async ({ page, browser }) => {
    await signIn(page, "manager");
    const title = uniqueTitle("live");
    await page.goto(`/tasks?q=${encodeURIComponent(title)}`);
    await expect(page.getByText("Live", { exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("link", { name: title })).toHaveCount(0);

    // Another session (a different browser context) creates the task.
    const other = await browser.newContext();
    const otherPage = await other.newPage();
    await signIn(otherPage, "admin");
    const id = await apiCreateTask(otherPage, title);

    // Polling runs every 15s; appearing within 6s can only be the push.
    await expect(page.getByRole("link", { name: title })).toBeVisible({ timeout: 6_000 });

    await apiDeleteTask(otherPage, id);
    await other.close();
  });

  test("the stream refuses unauthenticated clients", async ({ request }) => {
    const res = await request.get(`${API}/events/stream`);
    expect(res.status()).toBe(401);
  });
});
