"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function EnvironmentsPage() {
  const [list, setList] = useState<any[]>([]);
  const [form, setForm] = useState({ name: "", base_url: "", allowed_domains: "", env_type: "sandbox", notes: "" });
  const [msg, setMsg] = useState("");

  const load = () => api("/environments").then(setList).catch((e) => setMsg(e.message));
  useEffect(() => { load(); }, []);

  const create = async () => {
    const body = {
      ...form,
      allowed_domains: form.allowed_domains.split(/[,\s]+/).filter(Boolean),
    };
    await api("/environments", { method: "POST", body: JSON.stringify(body) });
    setForm({ name: "", base_url: "", allowed_domains: "", env_type: "sandbox", notes: "" });
    load();
  };

  const test = async (id: number) => {
    const r = await api(`/environments/${id}/test`, { method: "POST" });
    setMsg(JSON.stringify(r));
    load();
  };

  return (
    <div className="space-y-4">
      <div className="card space-y-2">
        <h2 className="font-semibold">新建环境 · Sandbox/Staging/Internal only</h2>
        <p className="help-field">Preply.com 仅作 UI 参考，请勿将正式站设为默认支付环境。allowed_domains 为浏览器白名单。</p>
        <div className="grid md:grid-cols-2 gap-2">
          <input placeholder="名称" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input placeholder="Base URL" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} />
          <input placeholder="allowed_domains (comma)" value={form.allowed_domains} onChange={(e) => setForm({ ...form, allowed_domains: e.target.value })} />
          <select value={form.env_type} onChange={(e) => setForm({ ...form, env_type: e.target.value })}>
            <option value="sandbox">sandbox</option>
            <option value="staging">staging</option>
            <option value="internal">internal</option>
          </select>
        </div>
        <button className="btn" onClick={create}>创建</button>
      </div>
      {msg && <p className="text-sm text-surface-muted">{msg}</p>}
      <div className="card overflow-x-auto">
        <table className="data">
          <thead><tr><th>ID</th><th>名称</th><th>URL</th><th>类型</th><th>白名单</th><th>探测</th><th></th></tr></thead>
          <tbody>
            {list.map((e) => (
              <tr key={e.id}>
                <td>{e.id}</td><td>{e.name}</td><td className="max-w-xs truncate">{e.base_url}</td>
                <td>{e.env_type}</td><td>{(e.allowed_domains || []).join(", ")}</td>
                <td>{e.last_test_status || "-"}</td>
                <td className="space-x-2">
                  <button className="btn-ghost text-xs" onClick={() => test(e.id)}>Test</button>
                  <button className="btn-ghost text-xs text-accent-bad" onClick={async () => { await api(`/environments/${e.id}`, { method: "DELETE" }); load(); }}>删</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
