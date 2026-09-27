"use client";
import { useEffect, useState } from "react";
import { api, apiBlob } from "@/lib/api";

type TD = {
  id: number; pan_masked: string; pan_last4: string; expiry: string;
  brand?: string; selected: boolean; used_count: number; status: string; created_at: string;
};

export default function TestDataPage() {
  const [rows, setRows] = useState<TD[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [msg, setMsg] = useState("");

  const load = async () => {
    setRows(await api("/test-data"));
    setStats(await api("/test-data/stats"));
  };
  useEffect(() => { load(); }, []);

  const doPreview = async () => {
    setPreview(await api("/test-data/import-preview", { method: "POST", body: JSON.stringify({ text }) }));
  };
  const doConfirm = async () => {
    const r = await api<any>("/test-data/import-confirm", { method: "POST", body: JSON.stringify({ text, skip_dupes: true }) });
    setMsg(`导入 ${r.created} · 重复 ${r.skipped_dupes} · 错误 ${r.errors}`);
    setPreview(null); setText(""); load();
  };

  const toggle = (id: number) => {
    const n = new Set(selected);
    if (n.has(id)) n.delete(id); else n.add(id);
    setSelected(n);
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <h1 className="text-xl font-bold">测试数据 Test Data</h1>
      <p className="text-sm text-amber-300">仅用于 Sandbox/QA/Staging/Internal。CVC 永不出现在列表/日志/导出。禁止生产站真实提交。</p>
      <p className="text-sm text-surface-muted">格式: 卡号|MM/YY|CVC 或 CSV。例: 4242424242424242|12/30|123</p>

      {stats && (
        <div className="text-sm card">
          总计 {stats.total} · 未用 {stats.unused} · 已用 {stats.used} · 已选 {stats.selected} · 无效 {stats.invalid}
        </div>
      )}

      <div className="card space-y-3">
        <textarea className="input min-h-[100px] font-mono text-sm"
          placeholder={"4242424242424242|12/30|123\n4000000000000002|01/28|456"}
          value={text} onChange={(e) => setText(e.target.value)} />
        <div className="flex gap-2">
          <button className="btn" onClick={doPreview}>预览</button>
          {preview && <button className="btn" onClick={doConfirm}>确认导入 ({preview.valid})</button>}
          <button className="btn-ghost" onClick={async () => {
            const b = await apiBlob("/test-data/export-safe");
            const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "test_data_safe.csv"; a.click();
          }}>安全导出</button>
        </div>
        {preview && (
          <div className="text-sm">
            总计 {preview.total} · 有效 {preview.valid} · 重复 {preview.dupe} · 错误 {preview.error}
            <ul className="mt-2 max-h-40 overflow-auto text-xs">
              {preview.lines.map((l: any) => (
                <li key={l.line} className={l.status === "error" ? "text-rose-400" : l.status === "dupe" ? "text-amber-400" : ""}>
                  L{l.line} [{l.status}] {l.pan_masked || l.raw} {l.expiry || ""} {l.reason}
                </li>
              ))}
            </ul>
          </div>
        )}
        {msg && <p className="text-emerald-400 text-sm">{msg}</p>}
      </div>

      <div className="flex gap-2">
        <button className="btn-ghost" onClick={async () => {
          await api("/test-data/select", { method: "POST", body: JSON.stringify({ ids: [...selected], selected: true }) });
          load();
        }}>标记已选</button>
        <button className="btn-ghost" onClick={async () => {
          await api("/test-data/select", { method: "POST", body: JSON.stringify({ ids: rows.map((r) => r.id), selected: true }) });
          load();
        }}>全选</button>
        <button className="btn-ghost text-rose-400" onClick={async () => {
          if (!confirm("删除所选？")) return;
          await api("/test-data", { method: "DELETE", body: JSON.stringify({ ids: [...selected] }) });
          setSelected(new Set()); load();
        }}>删除所选</button>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-surface-muted border-b border-surface-border">
            <th></th><th>Card</th><th>Expiry</th><th>Brand</th><th>Status</th><th>Used</th><th>Selected</th>
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-surface-border/50">
                <td><input type="checkbox" checked={selected.has(r.id)} onChange={() => toggle(r.id)} /></td>
                <td className="py-2 font-mono">{r.pan_masked}</td>
                <td>{r.expiry}</td>
                <td>{r.brand || "—"}</td>
                <td>{r.status}</td>
                <td>{r.used_count}</td>
                <td>{r.selected ? "✓" : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
