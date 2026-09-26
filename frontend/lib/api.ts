/** Same-origin by default: browser calls /api/* on the Next.js host (port 3000).
 *  Next proxies to backend. Override with NEXT_PUBLIC_API_URL only for local special cases.
 */
const raw = (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) || "";
const API = (raw || "").replace(/\/$/, "");

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("pqa_token");
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) localStorage.setItem("pqa_token", t);
  else localStorage.removeItem("pqa_token");
}

export function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  // path is like /proxies or /health — always under /api
  return `${API}/api${p}`;
}

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string> || {}),
  };
  // Only set JSON content-type when we have a body and caller didn't set it
  if (opts.body && !headers["Content-Type"] && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(apiUrl(path), { ...opts, headers });
  if (res.status === 401 && typeof window !== "undefined" && !path.includes("/auth/login")) {
    setToken(null);
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const msg = typeof detail === "string" ? detail : (detail ? JSON.stringify(detail) : err.message || res.statusText);
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res.text() as any;
}

/** Download a binary/text export with auth. */
export async function downloadApi(path: string, filename: string) {
  const token = getToken();
  const res = await fetch(apiUrl(path), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export { API };
