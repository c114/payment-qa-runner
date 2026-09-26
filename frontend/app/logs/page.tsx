"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function LogsPage() {
  const [logs, setLogs] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [level, setLevel] = useState("");
  const [source, setSource] = useState("");

  useEffect(() => {
    const load = () => api("/logs?limit=300").then(setLogs);
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const filtered = logs.filter((l) => {
    if (level && (l.level || "").toUpperCase() !== level.toUpperCase()) return false;
    if (source && !(l.source || "").toLowerCase().includes(source.toLowerCase())) return false;
    if (q && !(l.message || "").toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="card space-y-3">
      <h2 className="font-semibold">系统日志（已脱敏）</h2>
      <div className="flex flex-wrap gap-2">
        <input placeholder="搜索消息..." value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        <select value={level} onChange={(e) => setLevel(e.target.value)}>
          <option value="">全部级别</option>
          <option value="INFO">INFO</option>
          <option value="WARN">WARN</option>
          <option value="ERROR">ERROR</option>
        </select>
        <input placeholder="source" value={source} onChange={(e) => setSource(e.target.value)} className="w-32" />
        <span className="text-xs text-surface-muted self-center">{filtered.length} / {logs.length}</span>
      </div>
      <div className="h-[70vh] overflow-auto font-mono text-xs space-y-1">
        {filtered.map((l) => (
          <div key={l.id}>
            <span className="text-surface-muted">{l.created_at}</span> [{l.level}] [{l.source}] {l.message}
          </div>
        ))}
        {!filtered.length && <div className="text-surface-muted">无匹配日志</div>}
      </div>
    </div>
  );
}
