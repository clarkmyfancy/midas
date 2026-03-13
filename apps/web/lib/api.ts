const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getApiBaseUrl() {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL;
  return baseUrl.replace(/\/$/, "");
}

export function resolveApiUrl(path: string) {
  return `${getApiBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
}

async function extractErrorMessage(response: Response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    const payload = (await response.json()) as { detail?: string; message?: string };
    return payload.detail || payload.message || `Request failed with status ${response.status}`;
  }

  const text = await response.text();
  return text || `Request failed with status ${response.status}`;
}

export async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  fetcher: typeof fetch = fetch,
) {
  const response = await fetcher(resolveApiUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...init.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(await extractErrorMessage(response), response.status);
  }

  return (await response.json()) as T;
}
