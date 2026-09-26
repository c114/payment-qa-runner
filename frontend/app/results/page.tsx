"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import clsx from "clsx";

export default function ResultsPage() {
  const [list, setList] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);
  useEffect(() => { api("/results").then(setList); }, []);

  return (
    <div className="space-y-4">
      <div className="card overflow-x-auto">
        <table className="data">
          <thead><tr><th>ID</th><th>Run</th><th>Case</th><th>Expected</th><th>Actual</th><th>Status</th><th>ms</th><th>PAN</th></tr></thead>
          <tbody>
            {list.map((r) => (
              <tr key={r.id} className="cursor-pointer" onClick={() => setDetail(r)}>
                <td>{r.id}</td><td>{r.run_id}</td><td>{r.case_id}</td>
                <td>{r.expected}</td><td>{r.actual}</td>
                <td className={clsx(r.status === "PASS" && "text-accent-good", r.status === "FAIL" && "text-accent-bad", r.status === "ERROR" && "text-accent-warn")}>{r.status}</td>
                <td>{Math.round(r.duration_ms)}</td><td>{r.pan_masked || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {detail && (
        <div className="card">
          <h3 className="font-semibold mb-2">步骤时间线 · {detail.case_id}</h3>
          <pre className="text-xs overflow-auto bg-black/40 p-3 rounded">{JSON.stringify(detail.steps, null, 2)}</pre>
          {detail.error_message && <p className="text-accent-bad text-sm mt-2">{detail.error_message}</p>}
        </div>
      )}
    </div>
  );
}
