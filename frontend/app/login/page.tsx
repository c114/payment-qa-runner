"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      const res = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(res.access_token);
      router.push("/");
    } catch (ex: any) {
      setErr(ex.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-4">
      <form onSubmit={submit} className="card w-full max-w-md space-y-4">
        <div>
          <h1 className="text-xl font-bold text-accent">Payment QA Runner</h1>
          <p className="text-sm text-surface-muted mt-1">管理员登录 · Admin Login</p>
        </div>
        <div>
          <label className="text-xs text-surface-muted">Email</label>
          <input className="w-full mt-1" value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </div>
        <div>
          <label className="text-xs text-surface-muted">Password</label>
          <input className="w-full mt-1" value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
        </div>
        {err && <p className="text-sm text-accent-bad">{err}</p>}
        <button className="btn w-full justify-center" disabled={loading}>{loading ? "..." : "登录 / Login"}</button>
      </form>
    </div>
  );
}
