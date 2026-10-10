"use client";

import React from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { cn } from "@/lib/cn";
import { THEMES, useTheme, type Theme } from "@/lib/theme";

const LABEL: Record<Theme, string> = { dark: "Dark", light: "Light", system: "System" };
const ICON = { dark: Moon, light: Sun, system: Monitor } as const;

/** Three-way segmented control: dark, light, or follow the operating system. */
export function ThemeSwitcher() {
  const [theme, setTheme] = useTheme();
  return (
    <div role="radiogroup" aria-label="Colour theme" className="inline-flex rounded-control border border-line bg-surface-2 p-0.5">
      {THEMES.map((t) => {
        const Icon = ICON[t];
        const active = theme === t;
        return (
          <button
            key={t}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setTheme(t)}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 rounded-[5px] px-3 text-xs transition-colors",
              active ? "bg-surface-3 font-medium text-fg shadow-sm" : "text-fg-muted hover:text-fg",
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {LABEL[t]}
          </button>
        );
      })}
    </div>
  );
}

/** Compact top-bar button: cycles dark, light, system. */
export function ThemeCycleButton() {
  const [theme, setTheme] = useTheme();
  const next = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
  const Icon = ICON[theme];
  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={`Theme: ${LABEL[theme]}. Switch to ${LABEL[next]}`}
      title={`Theme: ${LABEL[theme]}`}
      className="flex h-8 w-8 items-center justify-center rounded-control text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
    >
      <Icon className="h-4 w-4" aria-hidden />
    </button>
  );
}
