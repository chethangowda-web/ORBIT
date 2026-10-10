import type { Config } from "tailwindcss";

const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

/** Mission Control tokens (see docs/DESIGN_MISSION_CONTROL.md). */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: {
          1: token("surface-1"),
          2: token("surface-2"),
          3: token("surface-3"),
        },
        line: {
          DEFAULT: token("line"),
          subtle: token("line-subtle"),
        },
        fg: {
          DEFAULT: token("fg"),
          muted: token("fg-muted"),
          faint: token("fg-faint"),
        },
        accent: {
          DEFAULT: token("accent"),
          strong: token("accent-strong"),
        },
        ok: token("ok"),
        warn: token("warn"),
        danger: token("danger"),
        info: token("info"),
        high: token("high"),
      },
      borderRadius: {
        control: "6px",
        panel: "8px",
        modal: "10px",
      },
      fontFamily: {
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          '"Liberation Mono"',
          "monospace",
        ],
      },
      transitionDuration: {
        DEFAULT: "120ms",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-in-right": {
          from: { transform: "translateX(12px)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
      },
      animation: {
        "fade-in": "fade-in 120ms ease-out",
        "slide-in-right": "slide-in-right 120ms ease-out",
      },
    },
  },
  plugins: [],
};
export default config;
