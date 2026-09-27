"use client";
import { useEffect, useState } from "react";
import { api, downloadApi } from "@/lib/api";

export default function EnvironmentsPage() {
  const [list, setList] = useState<any[]>([]);
  const [form, setForm] = useState({ name: "", base_url: "", allowed_domains: "", env_type: "sandbox", notes: "" });
  const [edit, setEdit] = useState<any>(null);
  const [importText, setImportText] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => api("/environments").then(setList).catch((e) => setMsg(e.message));
  useEffect(() => { load(); }, []);

  const create = async () => {
    await api("/environments", { method: "POST", body: JSON.stringify({
      ...form, allowed_domains: form.allowed_domains.split(/[,\s]+/).filter(Boolean),
    }) });
    setForm({ name: "", base_url: "", allowed_domains: "", env_type: "sandbox", notes: "" });
    load();
  };

  return (
    <div className="space-y-4">
      <div className="card space-y-2">
        <h2 className="font-semibold">新建环境 · Sandbox/Staging/Internal only</h2>
        <p className="help-field">
          <b>是什么</b>：沙箱/预发/内网 QA 环境（Base URL + 域名白名单）。Preply.com 仅作 UI 参考。<br/>
          <b>是否必填</b>：name、base_url、allowed_domains、env_type 必填。<br/>
          <b>格式/示例</b>：Base URL <code>https://qa.example.test</code>；allowed_domains 逗号分隔 <code>qa.example.test,cdn.example.test</code>。<br/>
          <b>怎么操作</b>：填写 → 创建 → Test 探测；可导入/导出 JSON。Same-Origin 部署无需配置 CORS 公网 IP。
        </p>
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

      <div className="card space-y-2">
        <h3 className="font-semibold text-sm">导入 / 导出 JSON</h3>
        <textarea className="w-full h-24 font-mono text-xs" value={importText} onChange={(e) => setImportText(e.target.value)} placeholder='{"name":"...","base_url":"...","env_type":"sandbox"}' />
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={async () => { setMsg(JSON.stringify(await api("/environments/import", { method: "POST", body: JSON.stringify({ text: importText }) }))); load(); }}>导入</button>
          <button className="btn-ghost text-xs" onClick={() => downloadApi("/environments/export", "environments.json")}>导出</button>
          <button className="btn-ghost text-xs" onClick={async () => { const t = await api("/import/templates/environment"); setImportText(typeof t === "string" ? t : JSON.stringify(t, null, 2)); }}>模板</button>
        </div>
      </div>

      {msg && <p className="text-sm text-surface-muted whitespace-pre-wrap">{msg}</p>}
      <div className="card overflow-x-auto">
        <table className="data">
          <thead><tr><th>ID</th><th>名称</th><th>URL</th><th>类型</th><th>白名单</th><th>探测</th><th></th></tr></thead>
          <tbody>
            {list.map((e) => (
              <tr key={e.id}>
                <td>{e.id}</td><td>{e.name}</td><td className="max-w-xs truncate">{e.base_url}</td>
                <td>{e.env_type}</td><td>{(e.allowed_domains || []).join(", ")}</td>
                <td>{e.last_test_status || "-"}</td>
                <td className="space-x-1 whitespace-nowrap">
                  <button className="btn-ghost text-xs" onClick={async () => { setMsg(JSON.stringify(await api(`/environments/${e.id}/test`, { method: "POST" }))); load(); }}>Test</button>
                  <button className="btn-ghost text-xs" onClick={() => setEdit({ ...e, domains: (e.allowed_domains || []).join(", ") })}>编辑</button>
                  <button className="btn-ghost text-xs" onClick={async () => { await api(`/environments/${e.id}/clone`, { method: "POST" }); load(); }}>Clone</button>
                  <button className="btn-ghost text-xs text-accent-bad" onClick={async () => { await api(`/environments/${e.id}`, { method: "DELETE" }); load(); }}>删</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {edit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setEdit(null)}>
          <div className="card w-full max-w-lg space-y-2" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold">编辑环境</h3>
            <input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
            <input value={edit.base_url} onChange={(e) => setEdit({ ...edit, base_url: e.target.value })} />
            <input value={edit.domains} onChange={(e) => setEdit({ ...edit, domains: e.target.value })} placeholder="domains" />
            <select value={edit.env_type} onChange={(e) => setEdit({ ...edit, env_type: e.target.value })}>
              <option value="sandbox">sandbox</option>
              <option value="staging">staging</option>
              <option value="internal">internal</option>
            </select>
            <div className="flex gap-2">
              <button className="btn" onClick={async () => {
                await api(`/environments/${edit.id}`, { method: "PUT", body: JSON.stringify({
                  name: edit.name, base_url: edit.base_url, env_type: edit.env_type,
                  allowed_domains: edit.domains.split(/[,\s]+/).filter(Boolean),
                  is_active: edit.is_active, notes: edit.notes,
                }) });
                setEdit(null); load();
              }}>保存</button>
              <button className="btn-ghost" onClick={() => setEdit(null)}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
