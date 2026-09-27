"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const ENV_TYPES = ["Production", "Sandbox", "QA", "Staging", "Internal"];

const empty = {
  name: "", description: "", env_type: "Sandbox",
  base_url: "", login_url: "", target_url: "", task_type: "card_bind", enabled: true,
};

export default function TasksPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [help, setHelp] = useState<any>({});
  const [form, setForm] = useState<any>({ ...empty });
  const [editId, setEditId] = useState<number | null>(null);
  const [msg, setMsg] = useState("");

  const load = async () => {
    setRows(await api("/tasks"));
    setHelp(await api("/tasks/field-help"));
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    setMsg("");
    try {
      if (editId) {
        await api(`/tasks/${editId}`, { method: "PATCH", body: JSON.stringify(form) });
      } else {
        await api("/tasks", { method: "POST", body: JSON.stringify(form) });
      }
      setForm({ ...empty }); setEditId(null); load();
      setMsg("已保存");
    } catch (e: any) {
      setMsg(e.message);
    }
  };

  const fieldHint = (k: string) => {
    const h = help[k];
    if (!h) return null;
    return <p className="text-xs text-surface-muted mt-0.5">用途:{h["用途"]} · 格式:{h["格式"]} · 例:{h["示例"]} · 必填:{h["必填"] ? "是" : "否"}</p>;
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <h1 className="text-xl font-bold">任务 Tasks</h1>
      <p className="text-sm text-surface-muted">Production 任务禁止填卡提交。Sandbox/QA/Staging/Internal 可完整绑卡。</p>

      <div className="card space-y-3">
        <h2 className="font-semibold">{editId ? `编辑 #${editId}` : "新建任务"}</h2>
        {(["name", "description", "base_url", "login_url", "target_url"] as const).map((k) => (
          <div key={k}>
            <label className="text-sm capitalize">{k}</label>
            <input className="input" value={form[k] || ""} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
            {fieldHint(k)}
          </div>
        ))}
        <div>
          <label className="text-sm">env_type</label>
          <select className="input" value={form.env_type} onChange={(e) => setForm({ ...form, env_type: e.target.value, task_type: e.target.value === "Production" ? "smoke" : "card_bind" })}>
            {ENV_TYPES.map((e) => <option key={e} value={e}>{e}</option>)}
          </select>
          {fieldHint("env_type")}
        </div>
        <div>
          <label className="text-sm">task_type</label>
          <select className="input" value={form.task_type} onChange={(e) => setForm({ ...form, task_type: e.target.value })}>
            <option value="smoke">smoke</option>
            <option value="card_bind">card_bind</option>
          </select>
          {fieldHint("task_type")}
        </div>
        <div className="flex gap-2">
          <button className="btn" onClick={save}>保存</button>
          {editId && <button className="btn-ghost" onClick={() => { setEditId(null); setForm({ ...empty }); }}>取消</button>}
        </div>
        {msg && <p className="text-sm text-accent">{msg}</p>}
      </div>

      <div className="card space-y-3">
        {rows.map((t) => (
          <div key={t.id} className="border-b border-surface-border/50 pb-3">
            <div className="flex justify-between gap-2 flex-wrap">
              <div>
                <div className="font-semibold">{t.name} <span className="text-xs text-surface-muted">[{t.env_type}] {t.enabled ? "启用" : "禁用"}</span></div>
                <div className="text-xs text-surface-muted">{t.description}</div>
                <div className="text-xs">Target: {t.target_url}</div>
                <div className="text-xs">填卡: {t.allow_card_fill ? "是" : "否"} · {t.task_type}</div>
              </div>
              <div className="flex gap-2 flex-wrap">
                <button className="btn-ghost text-xs" onClick={() => { setEditId(t.id); setForm({ name: t.name, description: t.description || "", env_type: t.env_type, base_url: t.base_url, login_url: t.login_url, target_url: t.target_url, task_type: t.task_type, enabled: t.enabled }); }}>编辑</button>
                <button className="btn-ghost text-xs" onClick={async () => { const r = await api(`/tasks/${t.id}/test-url`, { method: "POST" }); setMsg(`URL测试: ${JSON.stringify(r)}`); load(); }}>测试地址</button>
                {t.enabled
                  ? <button className="btn-ghost text-xs" onClick={async () => { await api(`/tasks/${t.id}/disable`, { method: "POST" }); load(); }}>禁用</button>
                  : <button className="btn-ghost text-xs" onClick={async () => { await api(`/tasks/${t.id}/enable`, { method: "POST" }); load(); }}>启用</button>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
