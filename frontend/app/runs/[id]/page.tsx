"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, apiBlob } from "@/lib/api";
import Link from "next/link";

export default function RunDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const [run, setRun] = useState<any>(null);
  const [err, setErr] = useState("");

  const load = async () => {
    try { setRun(await api(`/runs/${id}`)); } catch (e: any) { setErr(e.message); }
  };
  useEffect(() => { load(); const iv = setInterval(load, 2000); return () => clearInterval(iv); }, [id]);

  if (!run) return <div>{err || "加载中…"}</div>;

  const live = ["QUEUED", "RUNNING", "STOPPING"].includes(run.status);

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold">Run #{run.id}</h1>
          <p className="text-sm text-surface-muted">
            {run.task_snapshot?.name} · {run.task_snapshot?.target_url} · {run.network_snapshot?.name} · Mode {run.mode}
          </p>
          <p className="text-sm">Started: {run.started_at ? new Date(run.started_at).toLocaleString() : "—"}</p>
        </div>
        <div className="flex gap-2">
          {live && (
            <button className="btn bg-rose-600" onClick={async () => { await api(`/runs/${id}/stop`, { method: "POST" }); load(); }}>
              STOP
            </button>
          )}
          <button className="btn-ghost" onClick={async () => {
            const b = await apiBlob(`/results/export?run_id=${id}&fmt=csv`);
            const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `run_${id}.csv`; a.click();
          }}>导出 CSV</button>
          <button className="btn-ghost" onClick={async () => {
            const b = await apiBlob(`/results/export?run_id=${id}&fmt=txt`);
            const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `run_${id}.txt`; a.click();
          }}>导出 TXT</button>
          {!live && (
            <button className="btn-ghost text-rose-400" onClick={async () => {
              if (!confirm("删除本 Run 及其结果/产物？（不删账号）")) return;
              await api(`/runs/${id}`, { method: "DELETE" });
              window.location.href = "/runs";
            }}>删除本 Run</button>
          )}
          <Link className="btn-ghost" href="/runs">返回</Link>
        </div>
      </div>

      <div className="card grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div>进度 <b>{run.progress_done}/{run.progress_total}</b></div>
        <div>当前账号 <b>{run.current_account || "—"}</b></div>
        <div>步骤 <b>{run.current_step || "—"}</b></div>
        <div>状态 <b>{run.status}</b></div>
        <div className="text-emerald-400">SUCCESS {run.success_count}</div>
        <div className="text-amber-400">FAIL {run.fail_count}</div>
        <div className="text-rose-400">ERROR {run.error_count}</div>
        <div>CANCELLED {run.cancelled_count}</div>
      </div>

      <div className="card">
        <h2 className="font-semibold mb-2">实时日志</h2>
        <pre className="text-xs max-h-48 overflow-auto bg-black/30 p-3 rounded">
          {(run.live_log || []).slice(-80).map((l: any, i: number) => `${l.ts} ${l.msg}`).join("\n") || "—"}
        </pre>
      </div>

      <div className="card overflow-x-auto">
        <h2 className="font-semibold mb-2">结果</h2>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-surface-muted border-b border-surface-border">
            <th className="py-2">Account</th><th>Test Data</th><th>Result</th><th>Code</th><th>Reason</th><th>State</th>
          </tr></thead>
          <tbody>
            {(run.items || []).map((it: any) => (
              <tr key={it.id} className="border-b border-surface-border/50">
                <td className="py-2">{it.account_email}</td>
                <td className="font-mono text-xs">{it.test_data_masked || "—"}</td>
                <td>{it.status}</td>
                <td className="text-xs">{it.result_code || "—"}</td>
                <td className="text-xs max-w-xs truncate">{it.reason || ""}</td>
                <td className="text-xs">{it.state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
