"use client";
import { useCallback, useEffect, useState } from "react";
import { api, API } from "@/lib/api";
import clsx from "clsx";

type Comp = { status: string; last_seen?: string };

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      setStats(await api("/dashboard/stats"));
      const h = await fetch(`${API}/api/health`).then((r) => r.json());
      setHealth(h);
      setErr("");
    } catch (e: any) {
      setErr(e.message);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [load]);

  const control = async (action: string) => {
    if (!stats?.active_run?.id) return;
    await api(`/test-runs/${stats.active_run.id}/${action}`, { method: "POST" });
    load();
  };

  const badge = (c?: Comp) => {
    const s = (c?.status || "unknown").toLowerCase();
    const color =
      s === "ok" ? "bg-accent-good text-black" :
      s === "idle" ? "bg-yellow-600/40 text-yellow-100" :
      s === "down" ? "bg-accent-bad text-white" : "bg-surface-border";
    return (
      <span className={clsx("px-2 py-0.5 rounded text-xs uppercase", color)} title={c?.last_seen}>
        {s}
      </span>
    );
  };

  if (err && !stats) return <p className="text-accent-bad">{err}</p>;
  if (!stats) return <p className="text-surface-muted">加载中...</p>;

  return (
    <div className="space-y-6">
      <div className="card">
        <h2 className="font-semibold mb-3">系统健康 · Health</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          {[
            ["backend", health?.backend],
            ["database", health?.database],
            ["worker", health?.worker],
            ["browser_worker", health?.browser_worker],
          ].map(([label, comp]) => (
            <div key={label as string} className="flex items-center justify-between gap-2 border border-surface-border rounded px-3 py-2">
              <span className="text-surface-muted">{label as string}</span>
              {badge(comp as Comp)}
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          ["运行中", stats.running_runs],
          ["通过", stats.pass_count],
          ["失败", stats.fail_count],
          ["错误", stats.error_count],
          ["就绪账号", stats.accounts_ready],
          ["在线代理", stats.proxies_online],
          ["环境", stats.environments],
          ["用例", stats.cases],
        ].map(([label, val]) => (
          <div key={label as string} className="card">
            <div className="text-xs text-surface-muted">{label}</div>
            <div className="text-2xl font-semibold mt-1">{val}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2 className="font-semibold mb-3">配置向导 · Wizard 1–11</h2>
        <div className="grid md:grid-cols-2 gap-2">
          {(stats.wizard || []).map((w: any) => (
            <div key={w.step} className="flex items-center gap-2 text-sm">
              <span className={clsx("w-5 h-5 rounded-full flex items-center justify-center text-xs", w.done ? "bg-accent-good text-black" : "bg-surface-border")}>
                {w.done ? "✓" : w.step}
              </span>
              <span>{w.label_zh}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold mb-3">运行控制 · Shortcuts</h2>
        {stats.active_run ? (
          <p className="text-sm text-surface-muted mb-2">
            #{stats.active_run.id} {stats.active_run.name} — {stats.active_run.status} ({stats.active_run.progress_done}/{stats.active_run.progress_total})
          </p>
        ) : (
          <p className="text-sm text-surface-muted mb-2">无活动运行。请到「测试运行」创建。</p>
        )}
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={() => control("START")}>START</button>
          <button className="btn-ghost" onClick={() => control("PAUSE")}>PAUSE</button>
          <button className="btn-ghost" onClick={() => control("RESUME")}>RESUME</button>
          <button className="btn-danger" onClick={() => control("STOP")}>STOP</button>
        </div>
      </div>
    </div>
  );
}
