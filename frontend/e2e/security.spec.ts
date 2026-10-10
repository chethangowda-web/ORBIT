import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.describe("browser security", () => {
  test("every screen loads with zero Content-Security-Policy violations", async ({ page }) => {
    const violations: string[] = [];
    page.on("console", (msg) => {
      if (/content security policy|refused to (load|execute|connect|apply)/i.test(msg.text())) violations.push(msg.text());
    });
    await page.addInitScript(() => {
      document.addEventListener("securitypolicyviolation", (e) => {
        console.error(`Content Security Policy violation: ${e.violatedDirective} blocked ${e.blockedURI}`);
      });
    });

    await signIn(page, "admin");
    for (const path of ["/", "/tasks", "/insights", "/traces", "/admin", "/admin?tab=users", "/profile"]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
    }
    expect(violations).toEqual([]);
  });

  test("responses send the security headers", async ({ request }) => {
    const res = await request.get("/login");
    const headers = res.headers();
    expect(headers["x-frame-options"]).toBe("DENY");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["x-powered-by"]).toBeUndefined();
    const csp = headers["content-security-policy"];
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toMatch(/script-src [^;]*'nonce-[A-Za-z0-9+/=]+'/);
    expect(csp).not.toMatch(/script-src[^;]*'unsafe-inline'/);
  });

  test("injected markup with an inline event handler cannot run script", async ({ page }) => {
    await signIn(page, "employee");
    const ran = await page.evaluate(async () => {
      const w = window as unknown as { __xss?: boolean };
      w.__xss = false;
      // What an attacker gets from unescaped HTML: an element whose handler fires immediately.
      const holder = document.createElement("div");
      holder.innerHTML = '<img src="/does-not-exist.png" onerror="window.__xss = true">';
      document.body.appendChild(holder);
      await new Promise((resolve) => setTimeout(resolve, 500));
      return w.__xss;
    });
    expect(ran).toBe(false);
  });

  test("a different nonce is issued for every response", async ({ request }) => {
    const nonce = async () => ((await request.get("/login")).headers()["content-security-policy"].match(/'nonce-([^']+)'/) ?? [])[1];
    expect(await nonce()).not.toBe(await nonce());
  });
});
