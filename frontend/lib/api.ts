import { API_CONFIGURED, API_URL } from "./config";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

const TOKEN_KEY = "qbt_admin_token";

export function getAdminToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}
export function setAdminToken(token: string) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage unavailable (private mode) - token just won't persist */
  }
}

function messageFrom(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; problems?: string[] };
    if (d.message) return d.problems?.length ? `${d.message}: ${d.problems.join("; ")}` : d.message;
  }
  if (Array.isArray(detail)) return detail.map((x) => x?.msg ?? JSON.stringify(x)).join("; ");
  return fallback;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  if (!API_CONFIGURED) {
    throw new ApiError(0, "NEXT_PUBLIC_API_URL is not set. Add it in your hosting provider's environment settings.");
  }
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getAdminToken();
  if (token) headers["X-Admin-Token"] = token;
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, `Cannot reach the backend at ${API_URL || "(unset)"}. Is it running, and is CORS configured?`);
  }
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = (await res.json())?.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, messageFrom(detail, `${res.status} ${res.statusText}`), detail);
  }
  return (await res.json()) as T;
}

export const apiGet = <T>(path: string) => request<T>("GET", path);
export const apiPost = <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {});
export const apiPatch = <T>(path: string, body: unknown) => request<T>("PATCH", path, body);
export const apiPut = <T>(path: string, body: unknown) => request<T>("PUT", path, body);
export const apiDelete = <T>(path: string) => request<T>("DELETE", path);

/** URL for direct downloads (CSV / HTML report). */
export const apiUrl = (path: string) => `${API_URL}/api${path}`;
