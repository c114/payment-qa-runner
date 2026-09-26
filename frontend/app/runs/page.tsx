"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function RunsPage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [envs, setEnvs] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [cases, setCases] = useState<any[]>([]);
  const [form, setForm] = useState({ name: "", environment_id: 0, account_id: 0, network_profile_id: 0, run_count: "1", case_ids: [] as string[] });
  const [selected, setSelected] = useState<any>(null);

  const load = async () => {
    setRuns(await api("/test-runs"));
    setEnvs(await api("/environments"));
    setAccounts(await api("/accounts"));
    setProfiles(await api("/network-profiles"));
    setCases(await api("/test-cases"));
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const t = setInterval(async () => {
      const r = await api("/test-runs");
      setRuns(r);
      setSelected((prev: any) => {
        if (!prev) return prev;
        return r.find((x: any) => x.id === prev.id) || prev;
      });
    }, 2000);
    return () => clearInterval(t);
  }, []);

  const create = async () => {
    const body = {
      name: form.name,
      environment_id: form.environment_id || envs[0]?.id,
      account_id: form.account_id || null,
      network_profile_id: form.network_profile_id || profiles[0]?.id || null,
      run_count: form.run_count,
      case_ids: form.case_ids.length ? form.case_ids : cases.map((c) => c.case_id),
    };
    await api("/test-runs", { method: "POST", body: JSON.stringify(body) });
    load();
  };

  const control = async (id: number, action: string) => {
    await api(`/test-runs/${id}/${action}`, { method: "POST" });
    load();
  };

  return (
    <div className="space-y-4">
      <div className="card space-y-2">
        <h2 className="font-semibold">创建测试运行</h2>
        <div className="grid md:grid-cols-3 gap-2">
          <input placeholder="名称" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select value={form.environment_id} onChange={(e) => setForm({ ...form, environment_id: Number(e.target.value) })}>
            <option value={0}>选择环境</option>
            {envs.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <select value={form.account_id} onChange={(e) => setForm({ ...form, account_id: Number(e.target.value) })}>
            <option value={0}>账号（可选）</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.email}</option>)}
          </select>
          <select value={form.network_profile_id} onChange={(e) => setForm({ ...form, network_profile_id: Number(e.target.value) })}>
            <option value={0}>网络配置</option>
            {profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select value={form.run_count} onChange={(e) => setForm({ ...form, run_count: e.target.value })}>
            {["1", "5", "10", "50", "ALL"].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <button className="btn" onClick={create}>创建</button>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <div className="card overflow-x-auto">
          <table className="data">
            <thead><tr><th>ID</th><th>状态</th><th>进度</th><th>P/F/E</th><th></th></tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="cursor-pointer" onClick={() => setSelected(r)}>
                  <td>{r.id}</td><td>{r.status}</td>
                  <td>{r.progress_done}/{r.progress_total}</td>
                  <td>{r.pass_count}/{r.fail_count}/{r.error_count}</td>
                  <td className="space-x-1" onClick={(e) => e.stopPropagation()}>
                    <button className="btn-ghost text-xs" onClick={() => control(r.id, "START")}>START</button>
                    <button className="btn-ghost text-xs" onClick={() => control(r.id, "PAUSE")}>PAUSE</button>
                    <button className="btn-ghost text-xs" onClick={() => control(r.id, "RESUME")}>RESUME</button>
                    <button className="btn-ghost text-xs text-accent-bad" onClick={() => control(r.id, "STOP")}>STOP</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3 className="font-semibold mb-2">Live Log</h3>
          <div className="h-80 overflow-auto font-mono text-xs bg-black/40 p-2 rounded space-y-1">
            {(selected?.live_log || []).slice().reverse().map((l: any, i: number) => (
              <div key={i}><span className="text-surface-muted">{l.ts}</span> {l.msg}</div>
            ))}
            {!selected && <div className="text-surface-muted">选择一次运行查看日志</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
