"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function PageMappingPage() {
  const [list, setList] = useState<any[]>([]);
  const [envs, setEnvs] = useState<any[]>([]);
  const [envId, setEnvId] = useState<number | "">("");
  const [msg, setMsg] = useState("");

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
    setMsg(JSON.stringify(r));
  };

  return (
    <div className="space-y-4">
      <div className="card">
        <h2 className="font-semibold">页面映射 · 对照 screenshots page-1…7</h2>
        <p className="help-field">示例选择器来自 Preply UI 参考，请按目标沙箱修改。Test Selector 仅定位，不支付。</p>
        <div className="mt-2 flex gap-2 items-center">
          <span className="text-xs text-surface-muted">Test 环境:</span>
          <select value={envId} onChange={(e) => setEnvId(e.target.value ? Number(e.target.value) : "")}>
            <option value="">选择环境</option>
            {envs.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
        </div>
        {msg && <p className="text-xs text-surface-muted mt-2">{msg}</p>}
      </div>
      <div className="space-y-3">
        {list.map((m) => (
          <div key={m.id} className="card space-y-2">
            <div className="flex justify-between">
              <div>
                <span className="font-mono text-accent text-sm">{m.key}</span>
                {m.is_example && <span className="ml-2 text-xs text-accent-warn">示例</span>}
                <div className="text-sm">{m.label}</div>
              </div>
              <div className="flex gap-2">
                <button className="btn-ghost text-xs" onClick={() => testSel(m)}>Test Selector</button>
                <button className="btn text-xs" onClick={() => save(m)}>保存</button>
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
