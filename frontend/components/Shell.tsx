"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Locale, mainNavItems, t } from "@/lib/i18n";
import { api, getToken, setToken } from "@/lib/api";
import clsx from "clsx";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [locale, setLocale] = useState<Locale>("zh");
  const isLogin = pathname === "/login";

  useEffect(() => {
    const saved = localStorage.getItem("pqa_locale") as Locale | null;
    if (saved === "en" || saved === "zh") setLocale(saved);
  }, []);

  useEffect(() => {
    if (!isLogin && !getToken()) router.replace("/login");
  }, [isLogin, router, pathname]);

  const switchLocale = (l: Locale) => {
    setLocale(l);
    localStorage.setItem("pqa_locale", l);
  };

  if (isLogin) return <>{children}</>;

  return (
    <div className="flex min-h-screen">
      <aside className="w-52 shrink-0 border-r border-surface-border bg-[#0c1017] p-3 flex flex-col">
        <div className="mb-4 px-2">
          <div className="text-sm font-bold tracking-wide text-accent">Payment Test Runner</div>
          <div className="text-xs text-surface-muted">Version 2.0.0</div>
        </div>
        <nav className="flex-1 space-y-0.5">
          {mainNavItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "block rounded-md px-2 py-1.5 text-sm",
                pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href))
                  ? "bg-accent/20 text-accent"
                  : "text-slate-300 hover:bg-surface-card"
              )}
            >
              {t(locale, item.key)}
            </Link>
          ))}
        </nav>
        <div className="mt-2 flex gap-1 px-1">
          <button className={clsx("btn-ghost text-xs !py-1", locale === "zh" && "border-accent")} onClick={() => switchLocale("zh")}>中文</button>
          <button className={clsx("btn-ghost text-xs !py-1", locale === "en" && "border-accent")} onClick={() => switchLocale("en")}>EN</button>
        </div>
        <button
          className="btn-ghost mt-2 w-full justify-center text-xs"
          onClick={() => { setToken(null); router.push("/login"); }}
        >
          {t(locale, "logout")}
        </button>
      </aside>
      <main className="flex-1 flex flex-col min-w-0">
        <div className="bg-emerald-700/80 text-white text-center text-xs py-1.5 px-4 tracking-wide">
          LIVE MODE — Version 2.0.0 · 真实 Chromium · 无 Mock 回退
        </div>
        <div className="flex-1 overflow-auto p-6">{children}</div>
      </main>
    </div>
  );
}
