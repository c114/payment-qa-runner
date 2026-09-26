"use client";
import { useEffect, useState } from "react";
import { api, downloadApi } from "@/lib/api";

export default function CasesPage() {
  const [list, setList] = useState<any[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [importText, setImportText] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [edit, setEdit] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ case_id: "", name: "", payment_test_ref: "", expected_result: "SUCCESS", tags: "", notes: "" });

  const load = () => api("/test-cases").then(setList);
  useEffect(() => { load(); }, []);
  const toggle = (id: number) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);

  return (
    <div className="space-y-4">
      <div className="card">
        <h2 className="font-semibold">测试用例</h2>
        <p className="help-field">PASS/FAIL = Expected vs Actual。DECLINED+DECLINED=PASS。3DS → Actual=3DS 立即结束，不求解 OTP。CVV 永不落库。</p>
      </div>

      <div className="card space-y-2">
        <h3 className="font-semibold text-sm">新建用例</h3>
        <div className="grid md:grid-cols-3 gap-2">
          <input placeholder="Case ID" value={form.case_id} onChange={(e) => setForm({ ...form, case_id: e.target.value })} />
          <input placeholder="名称" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input placeholder="Payment Ref" value={form.payment_test_ref} onChange={(e) => setForm({ ...form, payment_test_ref: e.target.value })} />
          <input placeholder="Expected" value={form.expected_result} onChange={(e) => setForm({ ...form, expected_result: e.target.value })} />
          <input placeholder="Tag" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
          <input placeholder="Notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
        <button className="btn" onClick={async () => {
          await api("/test-cases", { method: "POST", body: JSON.stringify({
            case_id: form.case_id, name: form.name || form.case_id, payment_test_ref: form.payment_test_ref,
            expected_result: form.expected_result, tags: form.tags ? form.tags.split(/[,;]/).map((t) => t.trim()).filter(Boolean) : [],
            extra: form.notes ? { notes: form.notes } : {},
          }) });
          setForm({ case_id: "", name: "", payment_test_ref: "", expected_result: "SUCCESS", tags: "", notes: "" });
          load();
        }}>创建</button>
      </div>

      <div className="card space-y-2">
        <h3 className="font-semibold text-sm">TXT/CSV 导入</h3>
        <textarea className="w-full h-28 font-mono text-xs" value={importText} onChange={(e) => setImportText(e.target.value)}
          placeholder={"case_id|name|ref|expected|brand|last4|expiry|tag|notes"} />
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={async () => setPreview(await api("/test-cases/preview", { method: "POST", body: JSON.stringify({ text: importText }) }))}>解析预览</button>
          <button className="btn" disabled={!preview} onClick={async () => {
            const r = await api("/test-cases/import", { method: "POST", body: JSON.stringify({ text: importText }) });
            setMsg(`created=${r.created} updated=${r.updated}`); setPreview(null); setImportText(""); load();
          }}>确认导入</button>
          <button className="btn-ghost text-xs" onClick={async () => { const t = await api("/import/templates/cases"); setImportText(typeof t === "string" ? t : String(t)); }}>模板</button>
          <button className="btn-ghost text-xs" onClick={() => downloadApi("/test-cases/export?fmt=txt", "test_cases.txt")}>导出 TXT</button>
          <button className="btn-ghost text-xs" onClick={() => downloadApi("/test-cases/export?fmt=csv", "test_cases.csv")}>导出 CSV</button>
        </div>
        {preview && <pre className="text-xs bg-black/40 p-3 rounded overflow-auto max-h-40">{JSON.stringify(preview, null, 2)}</pre>}
      </div>

      <div className="card space-y-2">
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost text-xs" disabled={!selected.length} onClick={async () => { await api("/test-cases/batch-enable", { method: "POST", body: JSON.stringify({ ids: selected, enabled: true }) }); load(); }}>批量启用</button>
          <button className="btn-ghost text-xs" disabled={!selected.length} onClick={async () => { await api("/test-cases/batch-enable", { method: "POST", body: JSON.stringify({ ids: selected, enabled: false }) }); load(); }}>批量禁用</button>
          <button className="btn-ghost text-xs text-accent-bad" disabled={!selected.length} onClick={async () => { await api("/test-cases/batch-delete", { method: "POST", body: JSON.stringify({ ids: selected }) }); setSelected([]); load(); }}>批量删除</button>
        </div>
        {msg && <p className="text-xs text-surface-muted">{msg}</p>}
        <div className="overflow-x-auto">
          <table className="data">
            <thead><tr>
              <th><input type="checkbox" checked={!!list.length && selected.length === list.length} onChange={() => setSelected(selected.length === list.length ? [] : list.map((c) => c.id))} /></th>
              <th>Case ID</th><th>名称</th><th>Reference</th><th>期望</th><th>Tag</th><th>Notes</th><th>启用</th><th></th>
            </tr></thead>
            <tbody>
              {list.map((c) => (
                <tr key={c.id}>
                  <td><input type="checkbox" checked={selected.includes(c.id)} onChange={() => toggle(c.id)} /></td>
                  <td className="font-mono text-xs">{c.case_id}</td>
                  <td>{c.name}</td><td>{c.payment_test_ref}</td><td>{c.expected_result}</td>
                  <td>{(c.tags || []).join(",") || "-"}</td>
                  <td>{(c.extra && c.extra.notes) || "-"}</td>
                  <td>{c.is_active ? "Y" : "N"}</td>
                  <td className="space-x-1">
                    <button className="btn-ghost text-xs" onClick={() => setEdit({ ...c, tagsStr: (c.tags || []).join(","), notes: (c.extra && c.extra.notes) || "" })}>编辑</button>
                    <button className="btn-ghost text-xs text-accent-bad" onClick={async () => { await api(`/test-cases/${c.id}`, { method: "DELETE" }); load(); }}>删</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {edit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setEdit(null)}>
          <div className="card w-full max-w-lg space-y-2" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold">编辑 {edit.case_id}</h3>
            <input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
            <input value={edit.payment_test_ref || ""} onChange={(e) => setEdit({ ...edit, payment_test_ref: e.target.value })} placeholder="ref" />
            <input value={edit.expected_result} onChange={(e) => setEdit({ ...edit, expected_result: e.target.value })} />
            <input value={edit.tagsStr || ""} onChange={(e) => setEdit({ ...edit, tagsStr: e.target.value })} placeholder="tags" />
            <input value={edit.notes || ""} onChange={(e) => setEdit({ ...edit, notes: e.target.value })} placeholder="notes" />
            <label className="flex gap-2 text-sm"><input type="checkbox" checked={!!edit.is_active} onChange={(e) => setEdit({ ...edit, is_active: e.target.checked })} /> 启用</label>
            <div className="flex gap-2">
              <button className="btn" onClick={async () => {
                await api(`/test-cases/${edit.id}`, { method: "PUT", body: JSON.stringify({
                  case_id: edit.case_id, name: edit.name, payment_test_ref: edit.payment_test_ref,
                  expected_result: edit.expected_result, card_brand: edit.card_brand, pan_masked: edit.pan_masked,
                  expiry: edit.expiry, is_active: edit.is_active,
                  tags: (edit.tagsStr || "").split(/[,;]/).map((t: string) => t.trim()).filter(Boolean),
                  extra: { ...(edit.extra || {}), notes: edit.notes || "" },
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
