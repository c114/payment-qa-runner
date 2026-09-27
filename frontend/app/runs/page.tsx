"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type Run = {
  id: number; status: string; progress_done: number; progress_total: number;
  success_count: number; fail_count: number; error_count: number;
  task_snapshot: any; created_at: string; started_at?: string;
};

export default function RunsPage() {
  const [rows, setRows] = useState<Run[]>([]);
  const load = async () => setRows(await api("/runs"));
  useEffect(() => { load(); const iv = setInterval(load, 5000); return () => clearInterval(iv); }, []);

  return (
    <div className="space-y-6 max-w-5xl">
      <h1 className="text-xl font-bold">运行记录 Runs</h1>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-surface-muted border-b border-surface-border">
            <th className="py-2">Run</th><th>Task</th><th>Status</th><th>Progress</th><th>S/F/E</th><th>Started</th>
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-surface-border/50">
                <td className="py-2"><Link className="text-accent" href={`/runs/${r.id}`}>#{r.id}</Link></td>
                <td>{r.task_snapshot?.name || r.task_snapshot?.key || "—"}</td>
                <td>{r.status}</td>
                <td>{r.progress_done}/{r.progress_total}</td>
                <td>{r.success_count}/{r.fail_count}/{r.error_count}</td>
                <td className="text-xs">{r.started_at ? new Date(r.started_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
