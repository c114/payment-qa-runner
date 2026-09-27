"use client";
import { Fragment, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, apiBlob } from "@/lib/api";
import Link from "next/link";

export default function RunDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const [run, setRun] = useState<any>(null);
  const [err, setErr] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = async () => {
    try { setRun(await api(`/runs/${id}`)); } catch (e: any) { setErr(e.message); }
  };
  useEffect(() => { load(); const iv = setInterval(load, 2000); return () => clearInterval(iv); }, [id]);

  if (!run) return <div>{err || "加载中…"}</div>;

  const live = ["QUEUED", "RUNNING", "STOPPING"].includes(run.status);
  const artUrl = (aid: number) => `/api/artifacts/${aid}/content`;

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold">Run #{run.id}</h1>
          <p className="text-sm text-surface-muted">
            {run.task_snapshot?.name} · Adapter {run.task_snapshot?.adapter_type || "—"} · {run.task_snapshot?.target_url} · {run.network_snapshot?.name} · Mode {run.mode}
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
        <h2 className="font-semibold mb-2">结果明细</h2>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-surface-muted border-b border-surface-border">
            <th className="py-2">Run ID</th>
            <th>Account</th>
            <th>Step</th>
            <th>Result</th>
            <th>Code</th>
            <th>Error / Reason</th>
            <th>Final URL</th>
            <th>Duration</th>
            <th>Artifacts</th>
          </tr></thead>
          <tbody>
            {(run.items || []).map((it: any) => (
              <Fragment key={it.id}>
                <tr className="border-b border-surface-border/50 cursor-pointer" onClick={() => setExpanded(expanded === it.id ? null : it.id)}>
                  <td className="py-2">#{it.run_id}</td>
                  <td>{it.account_email}</td>
                  <td className="text-xs">{it.state}</td>
                  <td>{it.status}</td>
                  <td className="text-xs">{it.result_code || "—"}</td>
                  <td className="text-xs max-w-[12rem] truncate" title={it.reason || ""}>{it.reason || "—"}</td>
                  <td className="text-xs max-w-[10rem] truncate" title={it.final_url || ""}>{it.final_url || "—"}</td>
                  <td className="text-xs">{it.duration_ms ? `${Math.round(it.duration_ms)}ms` : "—"}</td>
                  <td className="text-xs space-x-2" onClick={(e) => e.stopPropagation()}>
                    {it.screenshot_id ? <a className="text-accent underline" href={artUrl(it.screenshot_id)} target="_blank" rel="noreferrer">Screenshot</a> : <span className="text-surface-muted">Shot—</span>}
                    {it.trace_id ? <a className="text-accent underline" href={artUrl(it.trace_id)} target="_blank" rel="noreferrer">Trace</a> : <span className="text-surface-muted">Trace—</span>}
                    <button className="underline text-accent" onClick={() => setExpanded(expanded === it.id ? null : it.id)}>Log</button>
                  </td>
                </tr>
                {expanded === it.id && (
                  <tr>
                    <td colSpan={9} className="bg-black/20 p-3 text-xs">
                      <div className="font-semibold mb-1">Steps / Log</div>
                      <pre className="whitespace-pre-wrap">{(it.steps || []).map((s: any) => `${s.ts || ""} [${s.state}] ${s.msg}`).join("\n") || it.log_excerpt || "—"}</pre>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
