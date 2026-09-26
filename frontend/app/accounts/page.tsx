"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function AccountsPage() {
  const [list, setList] = useState<any[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [creation, setCreation] = useState({ enabled: false, test_email_domain: "", name_prefix: "qa" });
  const [msg, setMsg] = useState("");
  const load = () => { api("/accounts").then(setList); api("/account-creation").then(setCreation); };
  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-4">
      <div className="card space-y-2">
        <h2 className="font-semibold">新增 QA 账号</h2>
        <p className="help-field">密码加密存储；永不写入日志。</p>
        <div className="flex flex-wrap gap-2">
          <input placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input placeholder="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <button className="btn" onClick={async () => { await api("/accounts", { method: "POST", body: JSON.stringify({ email, password }) }); setPassword(""); load(); }}>创建</button>
        </div>
      </div>
      <div className="card space-y-2">
        <h2 className="font-semibold">账号自动创建（默认关闭）</h2>
        <p className="help-field">启用时必须设置测试邮箱域名，禁止 gmail/outlook/yahoo。</p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={creation.enabled} onChange={(e) => setCreation({ ...creation, enabled: e.target.checked })} /> 启用
        </label>
        <input placeholder="test_email_domain e.g. mail.qa-internal.test" value={creation.test_email_domain}
          onChange={(e) => setCreation({ ...creation, test_email_domain: e.target.value })} />
        <button className="btn" onClick={async () => {
          try { await api("/account-creation", { method: "PUT", body: JSON.stringify(creation) }); setMsg("已保存"); }
          catch (e: any) { setMsg(e.message); }
        }}>保存策略</button>
        {msg && <p className="text-xs text-surface-muted">{msg}</p>}
      </div>
      <div className="card overflow-x-auto">
        <table className="data">
          <thead><tr><th>ID</th><th>Email</th><th>状态</th><th>连续失败</th><th></th></tr></thead>
          <tbody>
            {list.map((a) => (
              <tr key={a.id}>
                <td>{a.id}</td><td>{a.email}</td><td>{a.status}</td><td>{a.consecutive_failures}</td>
                <td className="space-x-2">
                  <button className="btn-ghost text-xs" onClick={async () => setMsg(JSON.stringify(await api(`/accounts/${a.id}/test-login`, { method: "POST" })))}>Test Login</button>
                  <button className="btn-ghost text-xs text-accent-bad" onClick={async () => { await api(`/accounts/${a.id}`, { method: "DELETE" }); load(); }}>删</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
