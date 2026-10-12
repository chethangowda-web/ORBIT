import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { checkFile, MAX_UPLOAD_BYTES } from "@/components/tasks/Attachments";
import { ThemeSwitcher } from "@/components/ui/ThemeSwitcher";
import { formatBytes } from "@/lib/format";
import { parseTheme } from "@/lib/theme";

describe("checkFile", () => {
  it("accepts allowed documents and rejects everything risky", () => {
    expect(checkFile({ name: "spec.PDF", size: 1000 })).toBeNull();
    expect(checkFile({ name: "page.html", size: 10 })).toMatch(/not an allowed/);
    expect(checkFile({ name: "logo.svg", size: 10 })).toMatch(/not an allowed/);
    expect(checkFile({ name: "noextension", size: 10 })).toMatch(/not an allowed/);
  });

  it("enforces size limits", () => {
    expect(checkFile({ name: "a.zip", size: 0 })).toMatch(/empty/);
    expect(checkFile({ name: "a.zip", size: MAX_UPLOAD_BYTES + 1 })).toMatch(/larger/);
    expect(checkFile({ name: "a.zip", size: MAX_UPLOAD_BYTES })).toBeNull();
  });
});

describe("formatBytes", () => {
  it("scales units", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});

describe("theme", () => {
  beforeEach(() => {
    document.documentElement.dataset.theme = "dark";
    document.cookie = "orbit_theme=; max-age=0; path=/";
  });

  it("falls back to light for unknown values", () => {
    expect(parseTheme("light")).toBe("light");
    expect(parseTheme("system")).toBe("system");
    expect(parseTheme("dark")).toBe("dark");
    expect(parseTheme("neon")).toBe("light");
    expect(parseTheme(undefined)).toBe("light");
  });

  it("switching updates the document and persists the choice", () => {
    render(<ThemeSwitcher />);
    expect(screen.getByRole("radio", { name: /dark/i })).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("radio", { name: /light/i }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.cookie).toContain("orbit_theme=light");
    expect(screen.getByRole("radio", { name: /light/i })).toHaveAttribute("aria-checked", "true");
  });
});
