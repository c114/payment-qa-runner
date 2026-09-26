"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function ProxiesPage() {
  const [list, setList] = useState<any[]>([]);
  const [form, setForm] = useState({ host: "", port: 1080, username: "", password: "" });
  const [profiles, setProfiles] = useState<any[]>([]);
  const load = () => { api("/proxies").then(setList); api("/network-profiles").then(setProfiles); };
  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-4">
      <div className="card space-y-2">
        <h2 className="font-semibold">SOCKS5 池</h2>
        <p className="help-field">禁止从互联网抓取代理。仅 NETWORK_ERROR / PROXY_DOWN / CONNECTION_TIMEOUT 可自动切换 Network Profile。</p>
        <div className="flex flex-wrap gap-2">
          <input placeholder="host" value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} />
          <input type="number" placeholder="port" value={form.port} onChange={(e) => setForm({ ...form, port: Number(e.target.value) })} />
          <input placeholder="username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
          <input type="password" placeholder="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <button className="btn" onClick={async () => { await api("/proxies", { method: "POST", body: JSON.stringify(form) }); setForm({ ...form, password: "" }); load(); }}>添加</button>
        </div>
      </div>
      <div className="card overflow-x-auto">
        <table className="data">
          <thead><tr><th>ID</th><th>Host</th><th>Port</th><th>状态</th><th>延迟</th><th>Exit IP</th><th></th></tr></thead>
          <tbody>
            {list.map((p) => (
              <tr key={p.id}>
                <td>{p.id}</td><td>{p.host}</td><td>{p.port}</td><td>{p.status}</td>
                <td>{p.latency_ms != null ? `${p.latency_ms.toFixed(0)}ms` : "-"}</td><td>{p.exit_ip || "-"}</td>
                <td className="space-x-2">
                  <button className="btn-ghost text-xs" onClick={async () => { await api(`/proxies/${p.id}/test`, { method: "POST" }); load(); }}>Test</button>
                  <button className="btn-ghost text-xs text-accent-bad" onClick={async () => { await api(`/proxies/${p.id}`, { method: "DELETE" }); load(); }}>删</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h2 className="font-semibold mb-2">Network Profiles</h2>
        <ul className="text-sm space-y-1">
          {profiles.map((n) => <li key={n.id}>{n.name} — {n.mode}{n.is_default ? " (default)" : ""}</li>)}
        </ul>
      </div>
    </div>
  );
}
