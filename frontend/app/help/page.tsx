"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const PAGES = ["dashboard", "environments", "page-mapping", "accounts", "proxies", "test-cases", "payrails", "runner"];

export default function HelpPage() {
  const [items, setItems] = useState<any[]>([]);
  useEffect(() => {
    Promise.all(PAGES.map((p) => api(`/help/${p}`))).then(setItems);
  }, []);
  return (
    <div className="space-y-3">
      <div className="card">
        <h2 className="font-semibold">帮助中心 · Help Center</h2>
        <p className="help-field">中文默认。完整文档见仓库 README.md。</p>
      </div>
      {items.map((h) => (
        <div key={h.page} className="card">
          <h3 className="font-semibold text-accent">{h.page}</h3>
          <p className="text-sm mt-1">{h.zh}</p>
          <p className="text-xs text-surface-muted mt-2">{h.en}</p>
        </div>
      ))}
    </div>
  );
}
