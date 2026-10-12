import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import "./globals.css";
import { parseTheme, THEME_COOKIE } from "@/lib/theme-shared";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "ORBIT", template: "%s | ORBIT" },
  description: "Smart task management that works with Google Chat.",
};

export const viewport: Viewport = {
  colorScheme: "dark light",
};

// Nonce-based CSP needs the nonce on each response, so pages are rendered per request
// instead of being prerendered to static HTML.
export const dynamic = "force-dynamic";

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const theme = parseTheme(cookies().get(THEME_COOKIE)?.value);
  return (
    <html lang="en" data-theme={theme} suppressHydrationWarning>
      <body className="min-h-screen bg-bg text-fg antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
