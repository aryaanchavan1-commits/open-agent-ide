const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "";

function authHeaders(): Record<string, string> {
  return API_TOKEN ? { "X-API-Token": API_TOKEN } : {};
}

export const api = {
  base: API_URL,

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const res = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json", ...authHeaders(), ...(options.headers || {}) },
      ...options,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail || body.error || detail;
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    if (res.status === 204) return undefined as T;
    return res.json() as Promise<T>;
  },

  get: <T>(path: string) => api.request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    api.request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    api.request<T>(path, { method: "PATCH", body: body !== undefined ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => api.request<T>(path, { method: "DELETE" }),
};

export function sseUrl(projectId: number): string {
  const base = `${API_URL}/api/projects/${projectId}/events`;
  return API_TOKEN ? `${base}?token=${encodeURIComponent(API_TOKEN)}` : base;
}
