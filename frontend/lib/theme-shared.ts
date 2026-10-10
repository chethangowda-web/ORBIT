/** Theme constants and parsing. No "use client": the server layout uses these too. */

export const THEME_COOKIE = "orbit_theme";
export const THEMES = ["dark", "light", "system"] as const;
export type Theme = (typeof THEMES)[number];
export const DEFAULT_THEME: Theme = "dark";

export function parseTheme(value: string | null | undefined): Theme {
  return (THEMES as readonly string[]).includes(value ?? "") ? (value as Theme) : DEFAULT_THEME;
}
