"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function CasesPage() {
  const [list, setList] = useState<any[]>([]);
  const load = () => api("/test-cases").then(setList);
  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-4">
      <div className="card">
        <h2 className="font-semibold">测试用例</h2>
        <p className="help-field">PASS/FAIL = Expected vs Actual。DECLINED+DECLINED=PASS。3DS → Actual=3DS 立即结束，不求解 OTP。CVV 永不落库；PAN 显示为 **** **** **** 1234。</p>
      </div>
      <div className="card overflow-x-auto">
        <table className="data">
          <thead><tr><th>Case ID</th><th>名称</th><th>Payrails Ref</th><th>期望</th><th>PAN</th><th>启用</th><th></th></tr></thead>
          <tbody>
            {list.map((c) => (
              <tr key={c.id}>
                <td className="font-mono text-xs">{c.case_id}</td>
                <td>{c.name}</td><td>{c.payment_test_ref}</td><td>{c.expected_result}</td>
                <td>{c.pan_masked || "-"}</td><td>{c.is_active ? "Y" : "N"}</td>
                <td><button className="btn-ghost text-xs text-accent-bad" onClick={async () => { await api(`/test-cases/${c.id}`, { method: "DELETE" }); load(); }}>删</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
