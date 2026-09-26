"use client";
import { useEffect, useState } from "react";
import { api, downloadApi } from "@/lib/api";

export default function ProxiesPage() {
  const [list, setList] = useState<any[]>([]);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [form, setForm] = useState({ host: "", port: 1080, username: "", password: "", label: "" });
  const [edit, setEdit] = useState<any>(null);
  const [importText, setImportText] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const [step, setStep] = useState<"idle" | "preview">("idle");

  const load = () => {
    api("/proxies").then(setList);
    api("/network-profiles").then(setProfiles);
  };
  useEffect(() => { load(); }, []);

  const toggle = (id: number) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const toggleAll = () =>
    setSelected(selected.length === list.length ? [] : list.map((p) => p.id));

  const doPreview = async () => {
    const r = await api("/proxies/preview", { method: "POST", body: JSON.stringify({ text: importText }) });
    setPreview(r);
    setStep("preview");
  };
  const doConfirm = async () => {
    const r = await api("/proxies/import", { method: "POST", body: JSON.stringify({ text: importText }) });
    setMsg(`导入完成: created=${r.created} errors=${(r.errors || []).length}`);
    setImportText("");
    setPreview(null);
    setStep("idle");
    load();
  };

  return (
    <div className="space-y-4">
      <div className="card space-y-2">
        <h2 className="font-semibold">SOCKS5 池</h2>
        <p className="help-field">禁止从互联网抓取代理。仅 NETWORK_ERROR / PROXY_DOWN / CONNECTION_TIMEOUT 可自动切换 Network Profile。CARD_DECLINED / 3DS 等禁止自动换代理。</p>
        <div className="flex flex-wrap gap-2">
          <input placeholder="host" value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} />
          <input type="number" placeholder="port" value={form.port} onChange={(e) => setForm({ ...form, port: Number(e.target.value) })} />
          <input placeholder="username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
          <input type="password" placeholder="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <input placeholder="label" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} />
          <button className="btn" onClick={async () => { await api("/proxies", { method: "POST", body: JSON.stringify(form) }); setForm({ ...form, password: "" }); load(); }}>添加</button>
        </div>
      </div>

      <div className="card space-y-2">
        <h3 className="font-semibold text-sm">批量导入 TXT/CSV · Upload → Parse → Preview → Confirm</h3>
        <textarea className="w-full h-28 font-mono text-xs" value={importText} onChange={(e) => setImportText(e.target.value)}
          placeholder={"host:port\nhost:port:user:pass\nsocks5://user:pass@host:port"} />
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={doPreview}>解析预览</button>
          {step === "preview" && <button className="btn" onClick={doConfirm}>确认导入</button>}
          <button className="btn-ghost text-xs" onClick={async () => { const t = await api("/import/templates/proxies"); setImportText(typeof t === "string" ? t : String(t)); }}>模板</button>
        </div>
        {preview && (
          <div className="text-xs bg-black/40 p-3 rounded">
            <div>解析 {preview.parsed} 条 · 错误 {(preview.errors || []).length}</div>
            {(preview.errors || []).slice(0, 5).map((e: string, i: number) => <div key={i} className="text-accent-bad">{e}</div>)}
            <pre className="mt-2 overflow-auto max-h-40">{JSON.stringify(preview.items?.slice(0, 20), null, 2)}</pre>
          </div>
        )}
      </div>

      <div className="card space-y-2">
        <div className="flex flex-wrap gap-2 items-center">
          <button className="btn-ghost text-xs" onClick={async () => { setMsg(JSON.stringify(await api("/proxies/test-all", { method: "POST" }))); load(); }}>Test All</button>
          <button className="btn-ghost text-xs" disabled={!selected.length} onClick={async () => { await api("/proxies/batch-enable", { method: "POST", body: JSON.stringify({ ids: selected, enabled: true }) }); load(); }}>批量启用</button>
          <button className="btn-ghost text-xs" disabled={!selected.length} onClick={async () => { await api("/proxies/batch-enable", { method: "POST", body: JSON.stringify({ ids: selected, enabled: false }) }); load(); }}>批量禁用</button>
          <button className="btn-ghost text-xs text-accent-bad" disabled={!selected.length} onClick={async () => { await api("/proxies/batch-delete", { method: "POST", body: JSON.stringify({ ids: selected }) }); setSelected([]); load(); }}>批量删除</button>
          <button className="btn-ghost text-xs" onClick={() => downloadApi("/proxies/export?fmt=txt", "proxies.txt")}>导出 TXT</button>
          <button className="btn-ghost text-xs" onClick={() => downloadApi("/proxies/export?fmt=csv", "proxies.csv")}>导出 CSV</button>
        </div>
        {msg && <p className="text-xs text-surface-muted whitespace-pre-wrap">{msg}</p>}
        <div className="overflow-x-auto">
          <table className="data">
            <thead>
              <tr>
                <th><input type="checkbox" checked={selected.length === list.length && list.length > 0} onChange={toggleAll} /></th>
                <th>Host</th><th>Port</th><th>User</th><th>状态</th><th>延迟</th><th>Exit IP</th><th>Last Check</th><th>启用</th><th></th>
              </tr>
            </thead>
            <tbody>
              {list.map((p) => (
                <tr key={p.id}>
                  <td><input type="checkbox" checked={selected.includes(p.id)} onChange={() => toggle(p.id)} /></td>
                  <td>{p.host}</td><td>{p.port}</td><td>{p.username || "-"}</td>
                  <td>{p.status}</td>
                  <td>{p.latency_ms != null ? `${Number(p.latency_ms).toFixed(0)}ms` : "-"}</td>
                  <td>{p.exit_ip || "-"}</td>
                  <td className="text-xs">{p.last_tested_at ? new Date(p.last_tested_at).toLocaleString() : "-"}</td>
                  <td>{p.is_active ? "Y" : "N"}</td>
                  <td className="space-x-1 whitespace-nowrap">
                    <button className="btn-ghost text-xs" onClick={async () => { await api(`/proxies/${p.id}/test`, { method: "POST" }); load(); }}>Test</button>
                    <button className="btn-ghost text-xs" onClick={() => setEdit({ ...p, password: "" })}>编辑</button>
                    <button className="btn-ghost text-xs text-accent-bad" onClick={async () => { await api(`/proxies/${p.id}`, { method: "DELETE" }); load(); }}>删</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {edit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setEdit(null)}>
          <div className="card w-full max-w-md space-y-2" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold">编辑代理 #{edit.id}</h3>
            <input placeholder="host" value={edit.host} onChange={(e) => setEdit({ ...edit, host: e.target.value })} />
            <input type="number" value={edit.port} onChange={(e) => setEdit({ ...edit, port: Number(e.target.value) })} />
            <input placeholder="username" value={edit.username || ""} onChange={(e) => setEdit({ ...edit, username: e.target.value })} />
            <input type="password" placeholder="新密码(留空不变)" value={edit.password || ""} onChange={(e) => setEdit({ ...edit, password: e.target.value })} />
            <label className="flex gap-2 text-sm items-center">
              <input type="checkbox" checked={!!edit.is_active} onChange={(e) => setEdit({ ...edit, is_active: e.target.checked })} /> 启用
            </label>
            <div className="flex gap-2">
              <button className="btn" onClick={async () => {
                await api(`/proxies/${edit.id}`, { method: "PUT", body: JSON.stringify({
                  host: edit.host, port: edit.port, username: edit.username || null,
                  password: edit.password || null, label: edit.label, is_active: edit.is_active,
                }) });
                setEdit(null); load();
              }}>保存</button>
              <button className="btn-ghost" onClick={() => setEdit(null)}>取消</button>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <h2 className="font-semibold mb-2">Network Profiles</h2>
        <ul className="text-sm space-y-1">
          {profiles.map((n) => <li key={n.id}>{n.name} — {n.mode}{n.is_default ? " (default)" : ""}</li>)}
        </ul>
      </div>
    </div>
  );
}
