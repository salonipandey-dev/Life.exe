// Thin fetch wrapper. Every state-changing request carries the CSRF header the
// backend requires; the session lives in an HttpOnly cookie JavaScript cannot read.

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Field-level messages from a 422 response, keyed by field name. */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    if (!Array.isArray(this.details)) return out;
    for (const d of this.details as { loc?: unknown[]; msg?: string }[]) {
      const field = Array.isArray(d.loc) ? String(d.loc[d.loc.length - 1]) : "";
      if (field && d.msg && !out[field]) out[field] = d.msg.replace(/^Value error, /, "");
    }
    return out;
  }
}

export type Fetcher = (input: string, init?: RequestInit) => Promise<Response>;

const BASE = "/api/v1";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as { error?: { code?: string; message?: string; details?: unknown } };
    if (body?.error) return new ApiError(res.status, body.error.code ?? "error", body.error.message ?? res.statusText, body.error.details);
  } catch {
    /* non-JSON error body */
  }
  const fallback = res.status === 0 ? "Can't reach the server. Check your connection and try again." : `Request failed (${res.status}).`;
  return new ApiError(res.status, "http_error", fallback);
}

export function createClient(fetcher: Fetcher = (i, init) => fetch(i, init)) {
  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (UNSAFE.has(method)) headers["X-LifeExe-CSRF"] = "1";
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let res: Response;
    try {
      res = await fetcher(BASE + path, {
        method,
        headers,
        credentials: "same-origin",
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, "network_error", "Can't reach the server. Check your connection and try again.");
    }
    if (!res.ok) throw await parseError(res);
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }
  return {
    get: <T>(path: string) => request<T>("GET", path),
    post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
    patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
    del: <T>(path: string) => request<T>("DELETE", path),
  };
}

export const api = createClient();

export function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}
