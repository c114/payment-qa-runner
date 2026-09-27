"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import clsx from "clsx";

type Health = {
  status: string; version: string; mode: string;
  backend: string; database: string; worker: string; chromium: string; network: string;
  disk?: any;
};
type Task = { id: number; name: string; description?: string; target_url: string; env_type: string; allow_card_fill: boolean; enabled: boolean };
type Network = { id: number; name: string; protocol: string; last_test_status?: string; last_latency_ms?: number };
type Ready = {
  ready: boolean; reasons: string[];
  accounts_imported: number; accounts_selected: number;
  test_data_imported: number; test_data_available: number; test_data_selected: number;
  max_executable: number; checklist: Record<string, boolean>;
  task?: Task; network?: Network;
};

function Dot({ ok }: { ok: boolean }) {
  return <span className={clsx("inline-block w-2 h-2 rounded-full mr-1", ok ? "bg-emerald-400" : "bg-rose-400")} />;
}

export default function HomePage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [networks, setNetworks] = useState<Network[]>([]);
  const [taskId, setTaskId] = useState<number | "">("");
  const [networkId, setNetworkId] = useState<number | "">("");
  const [ready, setReady] = useState<Ready | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [activeRunId, setActiveRunId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [h, ts, ns] = await Promise.all([
        api<Health>("/health"),
        api<Task[]>("/tasks"),
        api<Network[]>("/networks"),
      ]);
      setHealth(h);
      setTasks(ts.filter((t) => t.enabled));
      setNetworks(ns);
      if (taskId === "" && ts.length) {
        const pref = ts.find((t) => t.name.includes("Sandbox")) || ts[0];
        setTaskId(pref.id);
      }
      if (networkId === "" && ns.length) {
        const d = ns.find((n) => n.protocol === "direct") || ns[0];
        setNetworkId(d.id);
      }
    } catch (e: any) {
      setErr(e.message);
    }
  }, [taskId, networkId]);

  const refreshReady = useCallback(async () => {
    if (!taskId) return;
    try {
      const q = new URLSearchParams({ task_id: String(taskId) });
      if (networkId) q.set("network_id", String(networkId));
      const r = await api<Ready>(`/home/readiness?${q}`);
      setReady(r);
    } catch (e: any) {
      setErr(e.message);
    }
  }, [taskId, networkId]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { refreshReady(); const iv = setInterval(refreshReady, 4000); return () => clearInterval(iv); }, [refreshReady]);
  useEffect(() => { const iv = setInterval(refresh, 10000); return () => clearInterval(iv); }, [refresh]);

  const start = async () => {
    setBusy(true); setErr("");
    try {
      const run = await api<any>("/runs", {
        method: "POST",
        body: JSON.stringify({ task_id: taskId, network_id: networkId || null }),
      });
      setActiveRunId(run.id);
      window.location.href = `/runs/${run.id}`;
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const selectedTask = tasks.find((t) => t.id === taskId);

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Payment Test Runner</h1>
        <p className="text-sm text-surface-muted mt-1">Version {health?.version || "2.0.0"} · Mode <span className="text-emerald-400 font-semibold">{health?.mode || "LIVE"}</span></p>
      </div>

      <div className="card grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
        {(["backend", "database", "worker", "chromium", "network"] as const).map((k) => (
          <div key={k} className="flex items-center">
            <Dot ok={(health as any)?.[k] === "OK" || (health as any)?.[k] === "UNKNOWN"} />
            <span className="capitalize">{k}</span>
            <span className="ml-auto text-xs text-surface-muted">{(health as any)?.[k] || "—"}</span>
          </div>
        ))}
        <div className="flex items-center">
          <Dot ok={(health?.disk?.free_gb ?? 1) > 0.5} />
          <span>Disk</span>
          <span className="ml-auto text-xs text-surface-muted">
            {health?.disk?.free_gb != null ? `${health.disk.free_gb} GB free` : "—"}
          </span>
        </div>
      </div>

      <div className="card space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-semibold">① 账号 Accounts</div>
            <div className="text-sm text-surface-muted">
              已导入 {ready?.accounts_imported ?? "—"} · 已选择 {ready?.accounts_selected ?? "—"}
            </div>
          </div>
          <div className="flex gap-2">
            <Link className="btn" href="/accounts">导入账号</Link>
            <Link className="btn-ghost" href="/accounts">选择账号</Link>
          </div>
        </div>
      </div>

      <div className="card space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-semibold">② 测试数据 Test Data</div>
            <div className="text-sm text-surface-muted">
              已导入 {ready?.test_data_imported ?? "—"} · 可用 {ready?.test_data_available ?? "—"} · 已选 {ready?.test_data_selected ?? "—"}
              {selectedTask?.allow_card_fill ? " · 本任务需要测试卡" : " · 冒烟任务可不选"}
            </div>
          </div>
          <Link className="btn" href="/test-data">导入测试数据</Link>
        </div>
      </div>

      <div className="card space-y-3">
        <div className="font-semibold">③ 任务 Task</div>
        <select className="input" value={taskId} onChange={(e) => setTaskId(Number(e.target.value))}>
          <option value="">选择任务…</option>
          {tasks.map((t) => (
            <option key={t.id} value={t.id}>{t.name} [{t.env_type}]</option>
          ))}
        </select>
        {selectedTask && (
          <div className="text-sm text-surface-muted">
            <div>Target: <code className="text-accent">{selectedTask.target_url}</code></div>
            <div>{selectedTask.description}</div>
          </div>
        )}
      </div>

      <div className="card space-y-3">
        <div className="font-semibold">④ 网络 Network</div>
        <select className="input" value={networkId} onChange={(e) => setNetworkId(Number(e.target.value))}>
          {networks.map((n) => (
            <option key={n.id} value={n.id}>
              {n.name} ({n.protocol}){n.last_test_status ? ` · ${n.last_test_status}` : ""}
            </option>
          ))}
        </select>
      </div>

      <div className="card space-y-2">
        <div className="font-semibold">⑤ 就绪检查 Ready</div>
        {ready && (
          <ul className="text-sm space-y-1">
            {[
              ["accounts", "账号"],
              ["test_data", "测试数据"],
              ["task", "Task"],
              ["target_url", "Target URL"],
              ["chromium", "Chromium"],
              ["network", "Network"],
            ].map(([k, label]) => (
              <li key={k}>
                {ready.checklist?.[k] ? "✓" : "×"} {label}
              </li>
            ))}
            <li className="text-surface-muted">最多可执行: {ready.max_executable}</li>
          </ul>
        )}
        {ready && !ready.ready && (
          <ul className="text-sm text-rose-300 list-disc pl-5">
            {ready.reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        )}
      </div>

      {err && <div className="text-rose-400 text-sm">{err}</div>}

      <button
        className="btn text-lg px-8 py-3 disabled:opacity-40"
        disabled={!ready?.ready || busy}
        onClick={start}
      >
        {busy ? "启动中…" : "START"}
      </button>
      {activeRunId && <p className="text-sm">Run #{activeRunId}</p>}
    </div>
  );
}
