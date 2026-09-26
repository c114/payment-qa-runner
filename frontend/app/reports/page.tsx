"use client";
import { useState } from "react";
import { downloadApi } from "@/lib/api";

export default function ReportsPage() {
  const [msg, setMsg] = useState("");
  const [runId, setRunId] = useState("");

  const download = async (fmt: string) => {
    try {
      const q = runId ? `&run_id=${encodeURIComponent(runId)}` : "";
      await downloadApi(`/reports/export?fmt=${fmt}${q}`, `report.${fmt === "xlsx" ? "xlsx" : fmt}`);
      setMsg(`已下载 ${fmt.toUpperCase()}`);
    } catch (e: any) {
      setMsg(e.message);
    }
  };

  return (
    <div className="card space-y-3">
      <h2 className="font-semibold">导出报告</h2>
      <p className="help-field">导出不含 secrets / 完整 PAN / CVV。支持 CSV / XLSX / JSON / HTML。</p>
      <div className="flex flex-wrap gap-2 items-center">
        <input className="w-40" placeholder="run_id (可选)" value={runId} onChange={(e) => setRunId(e.target.value)} />
        {["csv", "xlsx", "json", "html"].map((f) => (
          <button key={f} className="btn" onClick={() => download(f)}>{f.toUpperCase()}</button>
        ))}
      </div>
      {msg && <p className="text-xs text-surface-muted">{msg}</p>}
    </div>
  );
}
