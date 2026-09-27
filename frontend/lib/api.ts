const API_BASE = typeof window !== "undefined"
  ? (process.env.NEXT_PUBLIC_API_URL || "/api")
  : (process.env.BACKEND_URL ? `${process.env.BACKEND_URL}/api` : "http://127.0.0.1:8000/api");

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("pqa_token");
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) localStorage.setItem("pqa_token", t);
  else localStorage.removeItem("pqa_token");
}

export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> || {}),
  };
  if (!(init.body instanceof FormData) && !headers["Content-Type"] && init.method && init.method !== "GET") {
    headers["Content-Type"] = "application/json";
  }
  const tok = getToken();
  if (tok) headers["Authorization"] = `Bearer ${tok}`;
  const res = await fetch(`${API_BASE}${path.startsWith("/") ? path : "/" + path}`, { ...init, headers });
  if (res.status === 401) {
    setToken(null);
    if (typeof window !== "undefined" && !window.location.pathname.includes("/login")) {
      window.location.href = "/login";
    }
    throw new Error("未登录");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail || JSON.stringify(j);
    } catch { /* */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res.text() as any;
}

export async function apiBlob(path: string): Promise<Blob> {
  const headers: Record<string, string> = {};
  const tok = getToken();
  if (tok) headers["Authorization"] = `Bearer ${tok}`;
  const res = await fetch(`${API_BASE}${path.startsWith("/") ? path : "/" + path}`, { headers });
  if (!res.ok) throw new Error("下载失败");
  return res.blob();
}
