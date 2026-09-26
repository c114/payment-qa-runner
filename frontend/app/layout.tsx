import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/Shell";

export const metadata: Metadata = {
  title: "Payment QA Runner",
  description: "Sandbox payment automation QA tool",
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
