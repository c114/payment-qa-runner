"use client";
import { useEffect, useState } from "react";
import { api, apiBlob } from "@/lib/api";

type Acc = {
  id: number; email: string; status: string; selected: boolean;
  session_status: string; last_result?: string; created_at: string;
};

export default function AccountsPage() {
  const [rows, setRows] = useState<Acc[]>([]);
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [q, setQ] = useState("");
  const [msg, setMsg] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const load = async () => {
    const qs = q ? `?q=${encodeURIComponent(q)}` : "";
    setRows(await api(`/accounts${qs}`));
  };
  useEffect(() => { load(); }, []);

  const doPreview = async () => {
    setPreview(await api("/accounts/import-preview", { method: "POST", body: JSON.stringify({ text }) }));
  };
  const doConfirm = async () => {
    const r = await api<any>("/accounts/import-confirm", { method: "POST", body: JSON.stringify({ text, skip_dupes: true }) });
    setMsg(`导入成功 ${r.created}，跳过重复 ${r.skipped_dupes}，错误 ${r.errors}`);
    setPreview(null); setText(""); load();
  };

  const toggle = (id: number) => {
    const n = new Set(selected);
    if (n.has(id)) n.delete(id); else n.add(id);
    setSelected(n);
  };

  const selectAll = (sel: boolean) => {
    api("/accounts/select", { method: "POST", body: JSON.stringify({ ids: rows.map((r) => r.id), selected: sel }) }).then(load);
  };

  const selectChecked = async (sel: boolean) => {
    await api("/accounts/select", { method: "POST", body: JSON.stringify({ ids: [...selected], selected: sel }) });
    load();
  };

  const del = async () => {
    if (!confirm("确认删除所选账号？")) return;
    await api("/accounts", { method: "DELETE", body: JSON.stringify({ ids: [...selected] }) });
    setSelected(new Set()); load();
  };

  const clearSession = async (id: number) => {
    await api(`/accounts/${id}/session-clear`, { method: "POST" });
    load();
  };

  const exp = async () => {
    const b = await apiBlob("/accounts/export");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(b);
    a.download = "accounts.csv";
    a.click();
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <h1 className="text-xl font-bold">账号 Accounts</h1>
      <p className="text-sm text-surface-muted">格式: email|password 或 email----password。列表/导出/日志永不显示密码。</p>

      <div className="card space-y-3">
        <textarea className="input min-h-[120px] font-mono text-sm" placeholder={"user@example.com|secret\nuser2@example.com----secret2"} value={text} onChange={(e) => setText(e.target.value)} />
        <div className="flex gap-2 flex-wrap">
          <button className="btn" onClick={doPreview}>预览 Preview</button>
          {preview && <button className="btn" onClick={doConfirm}>确认导入 Confirm ({preview.valid} valid)</button>}
          <button className="btn-ghost" onClick={exp}>导出 CSV</button>
        </div>
        {preview && (
          <div className="text-sm">
            总计 {preview.total} · 有效 {preview.valid} · 重复 {preview.dupe} · 错误 {preview.error}
            <ul className="mt-2 max-h-40 overflow-auto text-xs space-y-1">
              {preview.lines.map((l: any) => (
                <li key={l.line} className={l.status === "error" ? "text-rose-400" : l.status === "dupe" ? "text-amber-400" : "text-emerald-400"}>
                  L{l.line} [{l.status}] {l.email || l.raw} {l.reason}
                </li>
              ))}
            </ul>
          </div>
        )}
        {msg && <p className="text-emerald-400 text-sm">{msg}</p>}
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        <input className="input max-w-xs" placeholder="搜索邮箱" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn-ghost" onClick={load}>搜索</button>
        <button className="btn-ghost" onClick={() => selectChecked(true)}>标记已选</button>
        <button className="btn-ghost" onClick={() => selectAll(true)}>全选</button>
        <button className="btn-ghost" onClick={() => selectAll(false)}>取消全选</button>
        <button className="btn-ghost text-rose-400" onClick={del}>删除所选</button>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-surface-muted border-b border-surface-border">
            <th className="py-2"></th><th>Email</th><th>Status</th><th>Session</th><th>Selected</th><th>Last result</th><th>Created</th><th></th>
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-surface-border/50">
                <td><input type="checkbox" checked={selected.has(r.id)} onChange={() => toggle(r.id)} /></td>
                <td className="py-2">{r.email}</td>
                <td>{r.status}</td>
                <td>{r.session_status}</td>
                <td>{r.selected ? "✓" : "—"}</td>
                <td className="text-xs">{r.last_result || "—"}</td>
                <td className="text-xs">{new Date(r.created_at).toLocaleString()}</td>
                <td><button className="btn-ghost text-xs" onClick={() => clearSession(r.id)}>清除 Session</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
