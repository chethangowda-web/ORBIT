"use client";

/**
 * Theme preference: dark (default), light, or system.
 * Stored in a cookie so the server can render the right theme on the first paint (no flash);
 * the data-theme attribute on <html> drives the CSS tokens in globals.css.
 */

import { useCallback, useEffect, useState } from "react";
import { DEFAULT_THEME, parseTheme, THEME_COOKIE, type Theme } from "./theme-shared";

export { DEFAULT_THEME, parseTheme, THEME_COOKIE, THEMES, type Theme } from "./theme-shared";

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.cookie = `${THEME_COOKIE}=${theme}; path=/; max-age=31536000; SameSite=Lax`;
}

export function useTheme(): [Theme, (next: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(DEFAULT_THEME);

  useEffect(() => {
    setTheme(parseTheme(document.documentElement.dataset.theme));
  }, []);

  const update = useCallback((next: Theme) => {
    applyTheme(next);
    setTheme(next);
  }, []);

  return [theme, update];
}
