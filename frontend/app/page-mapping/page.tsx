"use client";
import { useEffect, useState } from "react";
import { api, downloadApi } from "@/lib/api";

export default function PageMappingPage() {
  const [list, setList] = useState<any[]>([]);
  const [envs, setEnvs] = useState<any[]>([]);
  const [envId, setEnvId] = useState<number | "">("");
  const [msg, setMsg] = useState("");
  const [importText, setImportText] = useState("");
  const [create, setCreate] = useState({ key: "", label: "", selector: "", selector_type: "css", page_group: "general" });

  const load = () => {
    api("/page-mappings").then(setList);
    api("/environments").then(setEnvs);
  };
  useEffect(() => { load(); }, []);

  const save = async (m: any) => {
    await api(`/page-mappings/${m.id}`, { method: "PUT", body: JSON.stringify(m) });
    setMsg("已保存 " + m.key);
    load();
  };

  const testSel = async (m: any) => {
    const r = await api("/page-mappings/test-selector", {
      method: "POST",
      body: JSON.stringify({
        environment_id: envId || null,
        selector: m.selector,
        selector_type: m.selector_type,
        iframe_selector: m.iframe_selector,
      }),
    });
    setMsg(`Selector test: ${r.result || (r.found ? "FOUND" : "NOT_FOUND")} — ${r.message || ""}`);
  };

  return (
    <div className="space-y-4">
      <div className="card">
        <h2 className="font-semibold">页面映射 · 对照 screenshots page-1…7</h2>
        <p className="help-field">示例选择器来自 Preply UI 参考，请按目标沙箱修改。Test Selector 返回 FOUND|NOT_FOUND|TIMEOUT|IFRAME_ERROR，仅定位不支付。</p>
        <div className="mt-2 flex gap-2 items-center flex-wrap">
          <span className="text-xs text-surface-muted">Test 环境:</span>
          <select value={envId} onChange={(e) => setEnvId(e.target.value ? Number(e.target.value) : "")}>
            <option value="">选择环境</option>
            {envs.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button className="btn-ghost text-xs" onClick={() => downloadApi("/page-mappings/export", "page_mappings.json")}>导出 JSON</button>
        </div>
        {msg && <p className="text-xs text-surface-muted mt-2 whitespace-pre-wrap">{msg}</p>}
      </div>

      <div className="card space-y-2">
        <h3 className="font-semibold text-sm">新建映射</h3>
        <div className="grid md:grid-cols-3 gap-2">
          <input placeholder="key" value={create.key} onChange={(e) => setCreate({ ...create, key: e.target.value })} />
          <input placeholder="label" value={create.label} onChange={(e) => setCreate({ ...create, label: e.target.value })} />
          <input placeholder="selector" value={create.selector} onChange={(e) => setCreate({ ...create, selector: e.target.value })} />
        </div>
        <button className="btn" onClick={async () => {
          await api("/page-mappings", { method: "POST", body: JSON.stringify({ ...create, label: create.label || create.key }) });
          setCreate({ key: "", label: "", selector: "", selector_type: "css", page_group: "general" });
          load();
        }}>创建</button>
      </div>

      <div className="card space-y-2">
        <h3 className="font-semibold text-sm">导入 JSON</h3>
        <textarea className="w-full h-24 font-mono text-xs" value={importText} onChange={(e) => setImportText(e.target.value)} />
        <div className="flex gap-2">
          <button className="btn" onClick={async () => { setMsg(JSON.stringify(await api("/page-mappings/import", { method: "POST", body: JSON.stringify({ text: importText }) }))); load(); }}>导入</button>
          <button className="btn-ghost text-xs" onClick={async () => { const t = await api("/import/templates/page_mapping"); setImportText(typeof t === "string" ? t : JSON.stringify(t, null, 2)); }}>模板</button>
        </div>
      </div>

      <div className="space-y-3">
        {list.map((m) => (
          <div key={m.id} className="card space-y-2">
            <div className="flex justify-between flex-wrap gap-2">
              <div>
                <span className="font-mono text-accent text-sm">{m.key}</span>
                {m.is_example && <span className="ml-2 text-xs text-accent-warn">示例</span>}
                <div className="text-sm">{m.label}</div>
              </div>
              <div className="flex gap-2 flex-wrap">
                <button className="btn-ghost text-xs" onClick={() => testSel(m)}>Test Selector</button>
                <button className="btn-ghost text-xs" onClick={async () => { await api(`/page-mappings/${m.id}/copy`, { method: "POST" }); load(); }}>Copy</button>
                <button className="btn text-xs" onClick={() => save(m)}>保存</button>
                <button className="btn-ghost text-xs text-accent-bad" onClick={async () => { await api(`/page-mappings/${m.id}`, { method: "DELETE" }); load(); }}>删</button>
              </div>
            </div>
            <div className="grid md:grid-cols-3 gap-2">
              <select value={m.selector_type} onChange={(e) => { m.selector_type = e.target.value; setList([...list]); }}>
                <option value="css">css</option>
                <option value="text">text</option>
                <option value="playwright">playwright</option>
                <option value="iframe">iframe</option>
              </select>
              <input className="md:col-span-2" value={m.selector || ""} onChange={(e) => { m.selector = e.target.value; setList([...list]); }} placeholder="selector" />
              <input className="md:col-span-3" value={m.iframe_selector || ""} onChange={(e) => { m.iframe_selector = e.target.value; setList([...list]); }} placeholder="iframe_selector (optional)" />
            </div>
            {m.help_zh && <p className="help-field">{m.help_zh}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
