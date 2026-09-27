"use client";
import { useEffect, useState } from "react";
import { api, downloadApi } from "@/lib/api";

export default function AccountsPage() {
  const [list, setList] = useState<any[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [creation, setCreation] = useState({ enabled: false, test_email_domain: "", name_prefix: "qa" });
  const [importText, setImportText] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [tag, setTag] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => { api("/accounts").then(setList); api("/account-creation").then(setCreation); };
  useEffect(() => { load(); }, []);

  const toggle = (id: number) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);

  return (
    <div className="space-y-4">
      <div className="card space-y-2">
        <h2 className="font-semibold">新增 QA 账号</h2>
        <p className="help-field">
          <b>是什么</b>：QA 账号（邮箱/密码）。密码加密存储，永不写日志。<br/>
          <b>是否必填</b>：创建时 email+password 必填；display name 可选。<br/>
          <b>格式/示例</b>：<code>email@example.com|password</code> · <code>email@example.com----password</code> · <code>name|email|password</code> · <code>name|email|password|tag</code>。<br/>
          <b>怎么操作</b>：单条填写点创建，或批量粘贴 → 解析预览 → 确认导入。
        </p>
        <div className="flex flex-wrap gap-2">
          <input placeholder="name (可选)" value={name} onChange={(e) => setName(e.target.value)} />
          <input placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input placeholder="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <button className="btn" onClick={async () => {
            await api("/accounts", { method: "POST", body: JSON.stringify({ email, password, display_name: name || null }) });
            setPassword(""); load();
          }}>创建</button>
        </div>
      </div>

      <div className="card space-y-2">
        <h3 className="font-semibold text-sm">批量导入 · Preview → Confirm</h3>
        <textarea className="w-full h-28 font-mono text-xs" value={importText} onChange={(e) => setImportText(e.target.value)}
          placeholder={"qa1@test.local|Secret123\nQA Two|qa2@test.local|Secret456|pool-a"} />
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={async () => setPreview(await api("/accounts/preview", { method: "POST", body: JSON.stringify({ text: importText }) }))}>解析预览</button>
          <button className="btn" disabled={!preview} onClick={async () => {
            const r = await api("/accounts/import", { method: "POST", body: JSON.stringify({ text: importText }) });
            setMsg(`导入: created=${r.created}`); setPreview(null); setImportText(""); load();
          }}>确认导入</button>
          <button className="btn-ghost text-xs" onClick={async () => { const t = await api("/import/templates/accounts"); setImportText(typeof t === "string" ? t : String(t)); }}>模板</button>
        </div>
        {preview && <pre className="text-xs bg-black/40 p-3 rounded overflow-auto max-h-40">{JSON.stringify(preview, null, 2)}</pre>}
      </div>

      <div className="card space-y-2">
        <h2 className="font-semibold">账号自动创建（默认关闭）</h2>
        <p className="help-field">启用时必须设置测试邮箱域名，禁止 gmail/outlook/yahoo。</p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={creation.enabled} onChange={(e) => setCreation({ ...creation, enabled: e.target.checked })} /> 启用
        </label>
        <input placeholder="test_email_domain e.g. mail.qa-internal.test" value={creation.test_email_domain}
          onChange={(e) => setCreation({ ...creation, test_email_domain: e.target.value })} />
        <button className="btn" onClick={async () => {
          try { await api("/account-creation", { method: "PUT", body: JSON.stringify(creation) }); setMsg("已保存"); }
          catch (e: any) { setMsg(e.message); }
        }}>保存策略</button>
      </div>

      <div className="card space-y-2">
        <div className="flex flex-wrap gap-2 items-center">
          <button className="btn-ghost text-xs" disabled={!selected.length} onClick={async () => { await api("/accounts/batch-status", { method: "POST", body: JSON.stringify({ ids: selected, status: "READY" }) }); load(); }}>批量启用</button>
          <button className="btn-ghost text-xs" disabled={!selected.length} onClick={async () => { await api("/accounts/batch-status", { method: "POST", body: JSON.stringify({ ids: selected, status: "DISABLED" }) }); load(); }}>批量禁用</button>
          <input className="w-32" placeholder="tag" value={tag} onChange={(e) => setTag(e.target.value)} />
          <button className="btn-ghost text-xs" disabled={!selected.length || !tag} onClick={async () => { await api("/accounts/batch-tag", { method: "POST", body: JSON.stringify({ ids: selected, tag }) }); load(); }}>批量打标</button>
          <button className="btn-ghost text-xs text-accent-bad" disabled={!selected.length} onClick={async () => { await api("/accounts/batch-delete", { method: "POST", body: JSON.stringify({ ids: selected }) }); setSelected([]); load(); }}>批量删除</button>
          <button className="btn-ghost text-xs" onClick={() => downloadApi("/accounts/export?fmt=txt", "accounts.txt")}>导出 TXT</button>
          <button className="btn-ghost text-xs" onClick={() => downloadApi("/accounts/export?fmt=csv", "accounts.csv")}>导出 CSV</button>
        </div>
        {msg && <p className="text-xs text-surface-muted">{msg}</p>}
        <div className="overflow-x-auto">
          <table className="data">
            <thead><tr>
              <th><input type="checkbox" checked={selected.length === list.length && !!list.length} onChange={() => setSelected(selected.length === list.length ? [] : list.map((a) => a.id))} /></th>
              <th>ID</th><th>Name</th><th>Email</th><th>状态</th><th>Tag/Notes</th><th>连续失败</th><th></th>
            </tr></thead>
            <tbody>
              {list.map((a) => (
                <tr key={a.id}>
                  <td><input type="checkbox" checked={selected.includes(a.id)} onChange={() => toggle(a.id)} /></td>
                  <td>{a.id}</td><td>{a.display_name || "-"}</td><td>{a.email}</td><td>{a.status}</td>
                  <td>{a.notes || "-"}</td><td>{a.consecutive_failures}</td>
                  <td className="space-x-2">
                    <button className="btn-ghost text-xs" onClick={async () => setMsg(JSON.stringify(await api(`/accounts/${a.id}/test-login`, { method: "POST" })))}>Test Login</button>
                    <button className="btn-ghost text-xs text-accent-bad" onClick={async () => { await api(`/accounts/${a.id}`, { method: "DELETE" }); load(); }}>删</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
