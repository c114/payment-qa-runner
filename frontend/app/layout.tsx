import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/Shell";

export const metadata: Metadata = {
  title: "Payment Test Runner 2.0.0",
  description: "Import accounts → select task → START → real Chromium",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
