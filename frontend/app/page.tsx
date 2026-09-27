"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import clsx from "clsx";

type Task = {
  id: number; key: string; name: string; name_zh: string;
  description_zh?: string; task_type: string;
};
type Account = { id: number; email: string; status: string; session_status?: string };
type Network = { id: number; name: string; mode: string; is_default: boolean };
type QuickStatus = {
  run_id: number; status: string;
  progress_done: number; progress_total: number;
  current_account?: string; current_step?: string;
  success_count: number; fail_count: number; error_count: number;
  live_log: { ts?: string; msg: string }[];
  is_mock?: boolean; error_code?: string; error_message_zh?: string;
};

export default function StartPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [networks, setNetworks] = useState<Network[]>([]);
  const [taskId, setTaskId] = useState<number | "">("");
  const [selectedAccounts, setSelectedAccounts] = useState<number[]>([]);
  const [networkId, setNetworkId] = useState<number | "">("");
  const [paste, setPaste] = useState("");
  const [importMsg, setImportMsg] = useState("");
  const [preview, setPreview] = useState<{ count?: number; errors?: string[] } | null>(null);
  const [runId, setRunId] = useState<number | null>(null);
  const [status, setStatus] = useState<QuickStatus | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const [t, a, n] = await Promise.all([
        api<Task[]>("/task-presets"),
        api<Account[]>("/accounts"),
        api<Network[]>("/network-profiles").catch(() => api<Network[]>("/networks").catch(() => [])),
      ]);
      setTasks(t || []);
      setAccounts(a || []);
      setNetworks(n || []);
      if (!taskId && t?.length) {
        const local = t.find((x) => x.key === "local_chromium_smoke") || t[0];
        setTaskId(local.id);
      }
      if (!networkId && n?.length) {
        const d = n.find((x) => x.is_default) || n.find((x) => x.mode === "direct") || n[0];
        if (d) setNetworkId(d.id);
      }
      setErr("");
    } catch (e: any) {
      setErr(e.message);
    }
  }, [taskId, networkId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!runId) return;
    const poll = async () => {
      try {
        const s = await api<QuickStatus>(`/quick-run/${runId}`);
        setStatus(s);
        if (["COMPLETED", "FAILED", "STOPPED"].includes(s.status)) {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setBusy(false);
          load();
        }
      } catch { /* ignore */ }
    };
    poll();
    pollRef.current = setInterval(poll, 1500);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [runId, load]);

  const doPreview = async () => {
    setImportMsg("");
    try {
      const r = await api<any>("/import/preview", {
        method: "POST",
        body: JSON.stringify({ text: paste, type: "accounts" }),
      });
      setPreview({ count: (r.items || r.preview || []).length || r.count, errors: r.errors });
    } catch (e: any) {
      // fallback: accounts/preview
      try {
        const r = await api<any>("/accounts/preview", {
          method: "POST",
          body: JSON.stringify({ text: paste }),
        });
        setPreview({ count: (r.items || []).length, errors: r.errors });
      } catch (e2: any) {
        setImportMsg(e2.message || e.message);
      }
    }
  };

  const doImport = async () => {
    setImportMsg("");
    try {
      const r = await api<any>("/accounts/import", {
        method: "POST",
        body: JSON.stringify({ text: paste }),
      });
      setImportMsg(`已导入 ${r.created ?? r.imported ?? r.count ?? "?"} 个账号`);
      setPaste("");
      setPreview(null);
      await load();
    } catch (e: any) {
      setImportMsg(e.message);
    }
  };

  const toggleAccount = (id: number) => {
    setSelectedAccounts((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const start = async () => {
    if (!taskId) { setErr("请选择任务"); return; }
    const task = tasks.find((x) => x.id === taskId);
    if (task?.task_type !== "local_fixture" && selectedAccounts.length === 0) {
      setErr("请选择至少一个账号（或先导入）");
      return;
    }
    setBusy(true);
    setErr("");
    setStatus(null);
    try {
      const r = await api<{ run_id: number }>("/quick-run", {
        method: "POST",
        body: JSON.stringify({
          task_id: taskId,
          account_ids: selectedAccounts,
          network_profile_id: networkId || null,
        }),
      });
      setRunId(r.run_id);
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  };

  const stop = async () => {
    if (!runId) return;
    await api(`/quick-run/${runId}/stop`, { method: "POST" });
  };

  const selectedTask = tasks.find((x) => x.id === taskId);

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-xl font-semibold">开始测试</h2>
        <p className="text-sm text-surface-muted mt-1">
          导入账号 → 选择任务 → 点击开始。真实 Chromium 自动运行，无需配置选择器。
        </p>
      </div>

      {err && <div className="card border-accent-bad/50 text-accent-bad text-sm">{err}</div>}

      {/* Import */}
      <div className="card space-y-3">
        <h3 className="font-semibold">1. 导入测试账号</h3>
        <p className="help-field">
          <b>是什么</b>：QA 测试账号（邮箱+密码），加密存库，用于登录冒烟。<br/>
          <b>是否必填</b>：生产冒烟必填；本地夹具任务可不选。<br/>
          <b>格式/示例</b>：每行一个 — <code>email@example.com|password</code> 或 <code>email@example.com----password</code>；也支持 <code>name|email|password</code>。<br/>
          <b>怎么操作</b>：粘贴 → 预览 → 导入并加密保存 → 在下方勾选账号。
        </p>
        <textarea
          className="input w-full h-28 font-mono text-sm"
          placeholder={"user@example.com|Secret123\nuser2@example.com----Secret456"}
          value={paste}
          onChange={(e) => setPaste(e.target.value)}
        />
        <div className="flex gap-2 flex-wrap">
          <button className="btn-ghost" type="button" onClick={doPreview} disabled={!paste.trim()}>预览</button>
          <button className="btn" type="button" onClick={doImport} disabled={!paste.trim()}>导入并加密保存</button>
          {preview && (
            <span className="text-sm text-surface-muted self-center">
              预览 {preview.count ?? 0} 条{preview.errors?.length ? `，错误 ${preview.errors.length}` : ""}
            </span>
          )}
        </div>
        {importMsg && <p className="text-sm text-accent-good">{importMsg}</p>}
      </div>

      {/* Accounts select */}
      <div className="card space-y-3">
        <h3 className="font-semibold">2. 选择账号</h3>
        {accounts.length === 0 ? (
          <p className="text-sm text-surface-muted">暂无账号。本地夹具任务可不选账号。</p>
        ) : (
          <div className="max-h-40 overflow-y-auto space-y-1">
            {accounts.map((a) => (
              <label key={a.id} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-surface-card rounded px-2 py-1">
                <input
                  type="checkbox"
                  checked={selectedAccounts.includes(a.id)}
                  onChange={() => toggleAccount(a.id)}
                />
                <span className="flex-1 truncate">{a.email}</span>
                <span className="text-xs text-surface-muted">{a.status}</span>
                <span className={clsx(
                  "text-xs px-1.5 rounded",
                  a.session_status === "VALID" ? "bg-accent-good/30" :
                  a.session_status === "EXPIRED" ? "bg-amber-600/40" : "bg-surface-border"
                )}>
                  SESSION {a.session_status || "NONE"}
                </span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Task + network */}
      <div className="card space-y-3">
        <h3 className="font-semibold">3. 选择任务</h3>
        <p className="help-field">
          <b>是什么</b>：管理员预置的一键任务（冒烟 / 本地夹具 / 支付填表）。<br/>
          <b>是否必填</b>：必填。<br/>
          <b>怎么操作</b>：下拉选择 → 可选网络 Profile → 点「开始」。LIVE 时跑真实 Chromium；MOCK 横幅出现时结果不是真实 PASS。
        </p>
        <select
          className="input w-full"
          value={taskId}
          onChange={(e) => setTaskId(e.target.value ? Number(e.target.value) : "")}
        >
          <option value="">— 选择 —</option>
          {tasks.map((tk) => (
            <option key={tk.id} value={tk.id}>
              {tk.name_zh || tk.name} ({tk.task_type})
            </option>
          ))}
        </select>
        {selectedTask?.description_zh && (
          <p className="text-xs text-surface-muted">{selectedTask.description_zh}</p>
        )}
        <div>
          <label className="text-xs text-surface-muted">网络（可选）</label>
          <select
            className="input w-full mt-1"
            value={networkId}
            onChange={(e) => setNetworkId(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">直连 / 默认</option>
            {networks.map((n) => (
              <option key={n.id} value={n.id}>{n.name} ({n.mode})</option>
            ))}
          </select>
        </div>
      </div>

      {/* START / STOP */}
      <div className="flex gap-3 items-center">
        <button
          className="btn text-base px-8 py-3 font-bold"
          type="button"
          onClick={start}
          disabled={busy || !taskId}
        >
          {busy ? "运行中…" : "▶ 开始 START"}
        </button>
        <button className="btn-ghost" type="button" onClick={stop} disabled={!busy}>
          停止 STOP
        </button>
        {runId && <span className="text-xs text-surface-muted">run #{runId}</span>}
      </div>

      {/* Live status */}
      {status && (
        <div className="card space-y-4">
          {status.is_mock && (
            <div className="bg-amber-500 text-black text-center text-sm font-bold py-2 rounded">
              ⚠ MOCK MODE — 此结果不是真实浏览器 PASS
            </div>
          )}
          <div className="flex flex-wrap gap-4 text-sm">
            <div>状态：<b>{status.status}</b></div>
            <div>进度：{status.progress_done}/{status.progress_total}</div>
            <div>当前账号：{status.current_account || "—"}</div>
            <div>步骤：{status.current_step || "—"}</div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded border border-accent-good/40 p-3 text-center">
              <div className="text-xs text-surface-muted">成功</div>
              <div className="text-2xl font-bold text-accent-good">{status.success_count}</div>
            </div>
            <div className="rounded border border-accent-bad/40 p-3 text-center">
              <div className="text-xs text-surface-muted">失败</div>
              <div className="text-2xl font-bold text-accent-bad">{status.fail_count}</div>
            </div>
            <div className="rounded border border-amber-500/40 p-3 text-center">
              <div className="text-xs text-surface-muted">异常</div>
              <div className="text-2xl font-bold text-amber-400">{status.error_count}</div>
            </div>
          </div>
          {status.error_code && (
            <p className="text-sm text-accent-bad">
              {status.error_code}: {status.error_message_zh}
            </p>
          )}
          <div>
            <h4 className="text-sm font-semibold mb-2">实时日志</h4>
            <div className="bg-black/40 rounded p-3 max-h-56 overflow-y-auto font-mono text-xs space-y-1">
              {(status.live_log || []).slice(-40).map((l, i) => (
                <div key={i} className="text-slate-300">
                  {l.msg}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
