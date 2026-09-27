"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import clsx from "clsx";

const ACTIONS = [
  { id: "open", label: "Open" },
  { id: "restart_page", label: "Restart Page" },
  { id: "restart_browser", label: "Restart Browser" },
  { id: "clear_cookies", label: "Clear Cookies" },
  { id: "re_login", label: "Re-login" },
  { id: "switch_account", label: "Switch Account" },
  { id: "switch_network", label: "Switch Network" },
  { id: "close", label: "Close" },
];

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
  const [accounts, setAccounts] = useState<any[]>([]);
  const [networks, setNetworks] = useState<any[]>([]);
  const [name, setName] = useState("Session-1");
  const [msg, setMsg] = useState("");

  const load = () => {
    api("/browser-sessions").then(setList);
    api("/environments").then(setEnvs);
    api("/accounts").then(setAccounts);
    api("/network-profiles").then(setNetworks);
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  const act = async (sid: number, action: string) => {
    const body: any = { action };
    if (action === "switch_account" && accounts[0]) body.account_id = accounts[0].id;
    if (action === "switch_network" && networks[0]) body.network_profile_id = networks[0].id;
    const r = await api(`/browser-sessions/${sid}/action`, { method: "POST", body: JSON.stringify(body) });
    setMsg(r.message || action);
    load();
  };

  return (
    <div className="space-y-4">
      <div className="card space-y-2">
        <h2 className="font-semibold">浏览器会话</h2>
        <p className="help-field">
          <b>是什么</b>：长期浏览器会话（可 Open / Restart / Re-login / Switch Network）。<br/>
          <b>是否必填</b>：普通一键冒烟可不建会话；高级排障时使用。<br/>
          <b>状态说明</b>：STALE = Worker 重启或心跳超时，不会显示为 READY。<br/>
          <b>怎么操作</b>：New Session → Open；switch_network = 新建 context，不热补丁代理。PLAYWRIGHT_MOCK=1 时动作以 mock 排队。
        </p>
        <div className="flex gap-2 flex-wrap">
          <input value={name} onChange={(e) => setName(e.target.value)} />
          <button className="btn" onClick={async () => {
            await api("/browser-sessions", { method: "POST", body: JSON.stringify({ name, environment_id: envs[0]?.id }) });
            load();
          }}>New Session</button>
        </div>
        {msg && <p className="text-xs text-surface-muted">{msg}</p>}
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
                <button key={a.id} className="btn-ghost text-xs" onClick={() => act(s.id, a.id)}>{a.label}</button>
              ))}
            </div>
          </div>
        ))}
        {!list.length && <p className="text-surface-muted text-sm">暂无会话 — 点击 New Session</p>}
      </div>
    </div>
  );
}
