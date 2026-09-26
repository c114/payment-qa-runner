"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export default function ImportPage() {
  const [kind, setKind] = useState<"cases" | "accounts" | "proxies">("cases");
  const [text, setText] = useState("");
  const [result, setResult] = useState("");

  const run = async () => {
    const path = kind === "cases" ? "/test-cases/import" : kind === "accounts" ? "/accounts/import" : "/proxies/import";
    const r = await api(path, { method: "POST", body: JSON.stringify({ text }) });
    setResult(JSON.stringify(r, null, 2));
  };

  return (
    <div className="space-y-4">
      <div className="card space-y-3">
        <h2 className="font-semibold">TXT 导入</h2>
        <p className="help-field">参见 examples/ 目录样例。用例支持灵活列映射；CVV 列会被忽略。</p>
        <select value={kind} onChange={(e) => setKind(e.target.value as any)}>
          <option value="cases">测试用例</option>
          <option value="accounts">QA 账号</option>
          <option value="proxies">SOCKS5</option>
        </select>
        <textarea className="w-full h-64 font-mono text-xs" value={text} onChange={(e) => setText(e.target.value)} placeholder="粘贴 TXT 内容..." />
        <button className="btn" onClick={run}>导入</button>
        {result && <pre className="text-xs bg-black/40 p-3 rounded overflow-auto">{result}</pre>}
      </div>
    </div>
  );
}
