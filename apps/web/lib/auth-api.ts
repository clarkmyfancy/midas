import type {
  AuthLoginRequest,
  AuthRegisterRequest,
  AuthTokenResponse,
  AuthUserResponse,
} from "@midas/types";

import { requestJson } from "./api";
import { toAuthSession } from "./auth-session";

export async function registerWithApi(
  payload: AuthRegisterRequest,
  fetcher: typeof fetch = fetch,
) {
  const response = await requestJson<AuthTokenResponse>(
    "/api/v1/auth/register",
    {
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    },
    fetcher,
  );

  return toAuthSession(response);
}

export async function loginWithApi(
  payload: AuthLoginRequest,
  fetcher: typeof fetch = fetch,
) {
  const response = await requestJson<AuthTokenResponse>(
    "/api/v1/auth/login",
    {
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    },
    fetcher,
  );

  return toAuthSession(response);
}

export function getCurrentUser(accessToken: string, fetcher: typeof fetch = fetch) {
  return requestJson<AuthUserResponse>(
    "/api/v1/auth/me",
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      method: "GET",
    },
    fetcher,
  );
}
