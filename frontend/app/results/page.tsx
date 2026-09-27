"use client";
import { useEffect, useState } from "react";
import { api, apiUrl, getToken } from "@/lib/api";
import clsx from "clsx";

function artifactHref(path: string) {
  const q = encodeURIComponent(path);
  return apiUrl(`/artifacts/download?path=${q}`);
}

export default function ResultsPage() {
  const [list, setList] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);
  useEffect(() => { api("/results").then(setList); }, []);

  const openArtifact = async (path: string, filename: string) => {
    const token = getToken();
    const res = await fetch(artifactHref(path), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`下载失败 ${res.status}`);
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const d = detail?.detail || {};
  const errorCode = d.error_code || detail?.actual || detail?.error_message;
  const shots: string[] = detail?.screenshot_paths || d.screenshot_paths || [];
  const trace =
    d.trace_path ||
    (detail?.steps || []).find((s: any) => s?.step === "trace")?.path;

  return (
    <div className="space-y-4">
      <p className="help-field">
        点击行查看详情：error_code / error_message / current_step / final_url / page_title / 截图 / Trace。
        不再只显示裸 PAGE_ERROR。
      </p>
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
        <div className="card space-y-3">
          <h3 className="font-semibold">结果详情 · {detail.case_id}</h3>
          <div className="grid md:grid-cols-2 gap-2 text-sm">
            <div><span className="text-surface-muted">error_code</span><div className="font-mono">{errorCode || "-"}</div></div>
            <div><span className="text-surface-muted">error_message</span><div className="font-mono break-all">{d.error_message || detail.error_message || "-"}</div></div>
            <div><span className="text-surface-muted">current_step</span><div className="font-mono">{d.current_step || "-"}</div></div>
            <div><span className="text-surface-muted">final_url</span><div className="font-mono break-all text-xs">{d.final_url || "-"}</div></div>
            <div><span className="text-surface-muted">page_title</span><div className="font-mono">{d.page_title || "-"}</div></div>
            <div><span className="text-surface-muted">status / actual</span><div>{detail.status} / {detail.actual}</div></div>
          </div>
          {shots.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold mb-1">截图</h4>
              <ul className="text-xs space-y-1">
                {shots.map((p, i) => (
                  <li key={i}>
                    <button className="btn-ghost text-xs" type="button" onClick={() => openArtifact(p, p.split("/").pop() || "shot.png")}>
                      下载 {p.split("/").pop()}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {trace && (
            <div>
              <h4 className="text-sm font-semibold mb-1">Trace</h4>
              <button className="btn-ghost text-xs" type="button" onClick={() => openArtifact(trace, trace.split("/").pop() || "trace.zip")}>
                下载 Trace ZIP
              </button>
            </div>
          )}
          <h4 className="text-sm font-semibold">步骤时间线</h4>
          <pre className="text-xs overflow-auto bg-black/40 p-3 rounded">{JSON.stringify(detail.steps, null, 2)}</pre>
          {detail.error_message && <p className="text-accent-bad text-sm">{detail.error_message}</p>}
        </div>
      )}
    </div>
  );
}
