import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "ORBIT: Multi-Agent AI Task Management System",
  description: "Enterprise task management with Google Chat integration and multi-agent swarm intelligence.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#090D13] text-[#E5EAF1] min-h-screen antialiased flex flex-row selection:bg-blue-600/30 selection:text-blue-200">
        <Providers>
          <Sidebar />
          <main className="flex-1 min-w-0 min-h-screen flex flex-col bg-[#090D13]">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
