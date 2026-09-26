"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import clsx from "clsx";

const ACTIONS = ["open", "restart_page", "restart_browser", "clear_cookies", "re_login", "switch_account", "switch_network", "close"];

function statusClass(status: string) {
  const s = (status || "").toUpperCase();
  if (s === "STALE") return "bg-yellow-700/50 text-yellow-100";
  if (s === "READY" || s === "OPEN" || s === "RUNNING") return "bg-accent-good/30 text-accent-good";
  if (s === "ERROR") return "bg-accent-bad/40 text-accent-bad";
  return "bg-surface-border text-surface-muted";
}

export default function SessionsPage() {
  const [list, setList] = useState<any[]>([]);
  const [envs, setEnvs] = useState<any[]>([]);
  const [name, setName] = useState("Session-1");
  const load = () => { api("/browser-sessions").then(setList); api("/environments").then(setEnvs); };
  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-4">
      <div className="card space-y-2">
        <h2 className="font-semibold">浏览器会话</h2>
        <p className="help-field">
          STALE = Worker 重启或心跳超时，不会显示为 READY。switch_network = 新建 context，不热补丁代理。
        </p>
        <div className="flex gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} />
          <button className="btn" onClick={async () => {
            await api("/browser-sessions", { method: "POST", body: JSON.stringify({ name, environment_id: envs[0]?.id }) });
            load();
          }}>创建</button>
        </div>
      </div>
      <div className="space-y-3">
        {list.map((s) => (
          <div key={s.id} className="card">
            <div className="flex justify-between mb-2 gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                <span className="font-semibold">{s.name}</span>
                <span className="text-xs text-surface-muted">#{s.id}</span>
                <span className={clsx("text-xs px-2 py-0.5 rounded", statusClass(s.status))}>{s.status}</span>
              </div>
              <span className="text-xs text-surface-muted">
                {s.last_action || "-"} · hb {s.last_heartbeat ? new Date(s.last_heartbeat).toLocaleTimeString() : "—"}
              </span>
            </div>
            <div className="text-xs text-surface-muted mb-2">
              browser={s.browser_state || "—"} · context={s.context_state || "—"} · worker={s.worker_id || "—"}
            </div>
            <div className="flex flex-wrap gap-1">
              {ACTIONS.map((a) => (
                <button key={a} className="btn-ghost text-xs" onClick={async () => {
                  await api(`/browser-sessions/${s.id}/action`, { method: "POST", body: JSON.stringify({ action: a }) });
                  load();
                }}>{a}</button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
