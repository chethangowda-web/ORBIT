import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "ORBIT", template: "%s | ORBIT" },
  description: "Multi-agent task management with Google Chat integration.",
};

export const viewport: Viewport = {
  themeColor: "#0A0E14",
  colorScheme: "dark",
};

// Nonce-based CSP needs the nonce on each response, so pages are rendered per request
// instead of being prerendered to static HTML.
export const dynamic = "force-dynamic";

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-bg text-fg antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
