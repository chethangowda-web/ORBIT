import { expect, type Page } from "@playwright/test";

export const API = process.env.E2E_API_URL ?? "http://localhost:8001/api";

export const ACCOUNTS = {
  admin: { email: "admin@orbit.dev", password: "password123" },
  manager: { email: "sarah@orbit.dev", password: "password123" },
  employee: { email: "john@orbit.dev", password: "password123" },
} as const;

export type Who = keyof typeof ACCOUNTS;

export async function signIn(page: Page, who: Who) {
  await page.goto("/login");
  await page.getByLabel("Work email").fill(ACCOUNTS[who].email);
  await page.getByLabel("Password").fill(ACCOUNTS[who].password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: "Board", level: 1 }).first()).toBeVisible();
}

export const uniqueTitle = (prefix = "e2e") => `${prefix} ${Date.now().toString(36)}`;

/** Create a task through the API as the signed-in user and return its id. */
export async function apiCreateTask(page: Page, title: string): Promise<string> {
  return page.evaluate(
    async ({ taskTitle, api }) => {
      const token = localStorage.getItem("orbit_token");
      const res = await fetch(`${api}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ title: taskTitle, priority: "HIGH" }),
      });
      return (await res.json()).data.id as string;
    },
    { taskTitle: title, api: API },
  );
}

/** Soft-delete a task (requires a manager or admin session). */
export async function apiDeleteTask(page: Page, id: string) {
  await page.evaluate(
    async ({ taskId, api }) => {
      const token = localStorage.getItem("orbit_token");
      await fetch(`${api}/tasks/${taskId}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
    },
    { taskId: id, api: API },
  );
}
