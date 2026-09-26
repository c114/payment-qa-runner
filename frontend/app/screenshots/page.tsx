"use client";
import { useEffect, useState } from "react";
import { api, apiUrl, downloadApi, getToken } from "@/lib/api";

export default function ScreenshotsPage() {
  const [files, setFiles] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => api("/screenshots").then(setFiles).catch((e) => setMsg(e.message));
  useEffect(() => { load(); }, []);

  const filtered = files.filter((f) => !q || (f.name || "").toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-4">
      <div className="card space-y-2">
        <h2 className="font-semibold">运行截图（策略默认 FAIL+ERROR+3DS）</h2>
        <input placeholder="搜索文件名..." value={q} onChange={(e) => setQ(e.target.value)} className="max-w-sm" />
        {msg && <p className="text-xs text-accent-bad">{msg}</p>}
        <div className="overflow-x-auto">
          <table className="data">
            <thead><tr><th>名称</th><th>大小</th><th>路径</th><th></th></tr></thead>
            <tbody>
              {filtered.map((f) => (
                <tr key={f.path}>
                  <td className="font-mono text-xs">{f.name}</td>
                  <td>{f.size} B</td>
                  <td className="font-mono text-xs max-w-xs truncate">{f.path}</td>
                  <td>
                    <button className="btn-ghost text-xs" onClick={() => downloadApi(`/screenshots/download?path=${encodeURIComponent(f.path)}`, f.name)}>下载</button>
                  </td>
                </tr>
              ))}
              {!filtered.length && <tr><td colSpan={4} className="text-surface-muted">暂无运行截图</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3 className="font-semibold mb-2">UI 参考截图 page-1…7（docs/）</h3>
        <div className="grid md:grid-cols-3 gap-2">
          {[1, 2, 3, 4, 5, 6, 7].map((n) => {
            const src = apiUrl(`/docs/screenshots/page-${n}.png`);
            return (
              <div key={n} className="border border-surface-border rounded p-2 text-xs text-center">
                <div className="text-surface-muted mb-1">page-{n}.png</div>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={src}
                  alt={`page-${n}`}
                  className="w-full h-auto rounded opacity-90"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              </div>
            );
          })}
        </div>
        <p className="help-field mt-2">参考图通过 Same-Origin /api/docs/screenshots/ 提供；缺失时仅显示文件名。</p>
      </div>
    </div>
  );
}
