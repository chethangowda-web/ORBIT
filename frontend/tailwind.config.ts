import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        orbit: {
          bg: "#090D13",
          surface: "#111821",
          elevated: "#151F2C",
          border: "#263241",
          subtle: "#1C2633",
          accent: "#3B82F6",
          "accent-hover": "#2563EB",
          text: "#E5EAF1",
          secondary: "#94A3B8",
          muted: "#64748B",
        },
      },
      borderRadius: {
        btn: "5px",
        card: "7px",
      },
    },
  },
  plugins: [],
};
export default config;
