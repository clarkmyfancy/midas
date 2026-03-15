import type { AuthTokenResponse, AuthUserResponse } from "@midas/types";

export const AUTH_REFRESH_TOKEN_STORAGE_KEY = "midas.auth.refresh-token";

export type AuthSession = {
  accessToken: string;
  refreshToken: string;
  user: AuthUserResponse;
};

export type StorageLike = Pick<Storage, "getItem" | "removeItem" | "setItem">;

export function toAuthSession(payload: AuthTokenResponse): AuthSession {
  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    user: payload.user,
  };
}

export function getBrowserStorage(): StorageLike | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage;
}

export function loadRefreshToken(storage: StorageLike | null): string | null {
  return storage?.getItem(AUTH_REFRESH_TOKEN_STORAGE_KEY) ?? null;
}

export function saveRefreshToken(storage: StorageLike | null, refreshToken: string) {
  storage?.setItem(AUTH_REFRESH_TOKEN_STORAGE_KEY, refreshToken);
}

export function clearRefreshToken(storage: StorageLike | null) {
  storage?.removeItem(AUTH_REFRESH_TOKEN_STORAGE_KEY);
}
