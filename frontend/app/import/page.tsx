"use client";
import { useState } from "react";
import { api } from "@/lib/api";

const TYPES = [
  { id: "accounts", label: "QA 账号" },
  { id: "proxies", label: "SOCKS5 代理" },
  { id: "cases", label: "测试用例" },
  { id: "page_mapping", label: "页面映射 JSON" },
  { id: "environment", label: "环境 JSON" },
] as const;

export default function ImportPage() {
  const [kind, setKind] = useState<(typeof TYPES)[number]["id"]>("cases");
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState("");

  const loadTemplate = async () => {
    try {
      const t = await api(`/import/templates/${kind}`);
      setText(typeof t === "string" ? t : JSON.stringify(t, null, 2));
      setErr("");
    } catch (e: any) { setErr(e.message); }
  };

  const doPreview = async () => {
    try {
      setPreview(await api("/import/preview", { method: "POST", body: JSON.stringify({ text, type: kind }) }));
      setResult(null);
      setErr("");
    } catch (e: any) { setErr(e.message); }
  };

  const doConfirm = async () => {
    try {
      setResult(await api("/import/confirm", { method: "POST", body: JSON.stringify({ text, type: kind }) }));
      setErr("");
    } catch (e: any) { setErr(e.message); }
  };

  return (
    <div className="space-y-4">
      <div className="card space-y-3">
        <h2 className="font-semibold">统一导入中心 · Unified Import</h2>
        <p className="help-field">流程：选择类型 → 下载模板 / 粘贴 → 解析预览 → 校验 → 确认导入。CVV 列会被忽略；账号密码加密存储。</p>
        <div className="flex flex-wrap gap-2 items-center">
          <select value={kind} onChange={(e) => { setKind(e.target.value as any); setPreview(null); setResult(null); }}>
            {TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
          <button className="btn-ghost text-xs" onClick={loadTemplate}>下载模板</button>
        </div>
        <textarea className="w-full h-64 font-mono text-xs" value={text} onChange={(e) => setText(e.target.value)} placeholder="粘贴 TXT / CSV / JSON..." />
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={doPreview}>1. 解析预览</button>
          <button className="btn" disabled={!preview} onClick={doConfirm}>2. 确认导入</button>
        </div>
        {err && <p className="text-accent-bad text-sm">{err}</p>}
      </div>

      {preview && (
        <div className="card space-y-2">
          <h3 className="font-semibold text-sm">预览 · {preview.type}</h3>
          <p className="text-sm">解析 {preview.parsed} 条 · 错误 {(preview.errors || []).length}</p>
          {(preview.errors || []).length > 0 && (
            <ul className="text-xs text-accent-bad list-disc pl-4">
              {(preview.errors as string[]).slice(0, 20).map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          )}
          <pre className="text-xs bg-black/40 p-3 rounded overflow-auto max-h-60">{JSON.stringify(preview.items?.slice(0, 50), null, 2)}</pre>
        </div>
      )}

      {result && (
        <div className="card space-y-2">
          <h3 className="font-semibold text-sm">导入结果</h3>
          <pre className="text-xs bg-black/40 p-3 rounded overflow-auto">{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
