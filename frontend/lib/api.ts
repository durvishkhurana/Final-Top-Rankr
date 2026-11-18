export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`/api${path}`, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
  });
}

function detail(body: unknown, fallback: string): string {
  const d = (body as { detail?: unknown } | null)?.detail;
  if (typeof d === "string") return d;
  // FastAPI validation errors: [{loc, msg}, ...]
  if (Array.isArray(d)) return d.map((e) => `${e.loc?.at(-1)}: ${e.msg}`).join("; ");
  return fallback;
}

/** Calls the API. When the access token has expired it is refreshed once and the call retried. */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res = await request(path, init);
  if (res.status === 401 && !["/auth/login", "/auth/signup", "/auth/refresh"].includes(path)) {
    const refreshed = await request("/auth/refresh", { method: "POST" });
    if (refreshed.ok) res = await request(path, init);
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detail(body, res.statusText));
  return body as T;
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const patch = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "PATCH", body: JSON.stringify(body) });

export const put = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "PUT", body: JSON.stringify(body) });
