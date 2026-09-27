"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Summary = {
  accounts: number; runs: number; results: number;
  screenshots: number; traces: number; expired_sessions: number;
  environments: number; network_profiles: number; task_presets: number; admins: number;
  preserved_note?: string;
};

const FLAGS: { key: keyof Flags; label: string; help: string }[] = [
  { key: "accounts", label: "QA 账号", help: "删除全部 QA 账号及其会话文件。不可恢复（请先看备份）。" },
  { key: "runs", label: "测试运行", help: "删除 test_runs（会连带删除其 results）。" },
  { key: "results", label: "测试结果", help: "仅删除 test_results，保留运行记录。" },
  { key: "screenshots", label: "截图文件", help: "删除 data/screenshots 下 PNG。" },
  { key: "traces", label: "Trace 文件", help: "删除 logs/traces 下 Playwright zip。" },
  { key: "expired_sessions", label: "过期会话", help: "清除 session_status=EXPIRED 的 storage_state。" },
];

type Flags = {
  accounts: boolean; runs: boolean; results: boolean;
  screenshots: boolean; traces: boolean; expired_sessions: boolean;
};

export default function DataManagementPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [flags, setFlags] = useState<Flags>({
    accounts: false, runs: false, results: false,
    screenshots: false, traces: false, expired_sessions: false,
  });
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api<Summary>("/data-management/summary").then(setSummary).catch((e) => setMsg(e.message));
  useEffect(() => { load(); }, []);

  const anySelected = Object.values(flags).some(Boolean);

  const doCleanup = async () => {
    setBusy(true);
    setMsg("");
    try {
      const r = await api<any>("/data-management/cleanup", {
        method: "POST",
        body: JSON.stringify({ confirm: true, ...flags }),
      });
      setMsg(r.message || JSON.stringify(r));
      setFlags({ accounts: false, runs: false, results: false, screenshots: false, traces: false, expired_sessions: false });
      setConfirmOpen(false);
      await load();
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="card space-y-2">
        <h2 className="font-semibold">数据管理</h2>
        <p className="help-field">
          选择性清理冗余数据。默认不删除：管理员、环境、Network Profile、任务预设、系统设置、.env。
          任何删除前会自动备份 SQLite 数据库文件，并在结果中显示备份路径。
        </p>
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
            <div className="rounded border border-surface-border p-2">账号 <b>{summary.accounts}</b></div>
            <div className="rounded border border-surface-border p-2">运行 <b>{summary.runs}</b></div>
            <div className="rounded border border-surface-border p-2">结果 <b>{summary.results}</b></div>
            <div className="rounded border border-surface-border p-2">截图 <b>{summary.screenshots}</b></div>
            <div className="rounded border border-surface-border p-2">Traces <b>{summary.traces}</b></div>
            <div className="rounded border border-surface-border p-2">过期会话 <b>{summary.expired_sessions}</b></div>
            <div className="rounded border border-surface-border p-2 text-surface-muted col-span-2 md:col-span-3 text-xs">
              保留：环境 {summary.environments} · NetworkProfile {summary.network_profiles} · 任务 {summary.task_presets} · 管理员 {summary.admins}
            </div>
          </div>
        )}
      </div>

      <div className="card space-y-3">
        <h3 className="font-semibold text-sm">选择清理目标（默认全部不勾选）</h3>
        {FLAGS.map((f) => (
          <label key={f.key} className="flex items-start gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              className="mt-1"
              checked={flags[f.key]}
              onChange={(e) => setFlags({ ...flags, [f.key]: e.target.checked })}
            />
            <span>
              <span className="font-medium">{f.label}</span>
              <span className="help-field block">{f.help}</span>
            </span>
          </label>
        ))}
        <button
          className="btn bg-accent-bad/80"
          disabled={!anySelected || busy}
          onClick={() => setConfirmOpen(true)}
        >
          执行清理…
        </button>
      </div>

      {msg && (
        <div className="card text-sm whitespace-pre-wrap">
          <pre className="text-xs overflow-auto">{typeof msg === "string" ? msg : JSON.stringify(msg, null, 2)}</pre>
        </div>
      )}

      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setConfirmOpen(false)}>
          <div className="card max-w-md w-full mx-4 space-y-3" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold text-accent-bad">确认清理？</h3>
            <p className="text-sm">
              将删除：{FLAGS.filter((f) => flags[f.key]).map((f) => f.label).join("、") || "（无）"}。
              操作前会自动备份数据库。Admin / Environment / NetworkProfile / TaskPreset / 系统设置 / .env 不会被删除。
            </p>
            <div className="flex gap-2">
              <button className="btn bg-accent-bad/80" disabled={busy} onClick={doCleanup}>
                {busy ? "清理中…" : "确认删除"}
              </button>
              <button className="btn-ghost" onClick={() => setConfirmOpen(false)}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
