"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Locale, navItems, t } from "@/lib/i18n";
import { api, getToken, setToken } from "@/lib/api";
import clsx from "clsx";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [locale, setLocale] = useState<Locale>("zh");
  const [helpOpen, setHelpOpen] = useState(false);
  const [helpText, setHelpText] = useState("");
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

  const openHelp = async () => {
    const key = pathname === "/" ? "dashboard" : pathname.replace(/^\//, "").replace(/\//g, "-") || "default";
    try {
      const h = await api<{ zh: string; en: string }>(`/help/${key}`);
      setHelpText(locale === "zh" ? h.zh : h.en);
    } catch {
      setHelpText(locale === "zh" ? "查看 README / Help Center。" : "See README / Help Center.");
    }
    setHelpOpen(true);
  };

  if (isLogin) return <>{children}</>;

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-surface-border bg-[#0c1017] p-3 flex flex-col">
        <div className="mb-4 px-2">
          <div className="text-sm font-bold tracking-wide text-accent">Payment QA</div>
          <div className="text-xs text-surface-muted">Runner</div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "block rounded-md px-2 py-1.5 text-sm",
                pathname === item.href ? "bg-accent/20 text-accent" : "text-slate-300 hover:bg-surface-card"
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
        <header className="flex items-center justify-between border-b border-surface-border px-6 py-3">
          <h1 className="text-lg font-semibold">{t(locale, "appName")}</h1>
          <button className="btn-ghost" onClick={openHelp}>{t(locale, "helpBtn")}</button>
        </header>
        <div className="flex-1 overflow-auto p-6">{children}</div>
      </main>
      {helpOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setHelpOpen(false)}>
          <div className="card max-w-lg w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-base font-semibold mb-2">{t(locale, "help")}</h2>
            <p className="text-sm text-slate-300 whitespace-pre-wrap">{helpText}</p>
            <button className="btn mt-4" onClick={() => setHelpOpen(false)}>OK</button>
          </div>
        </div>
      )}
    </div>
  );
}
