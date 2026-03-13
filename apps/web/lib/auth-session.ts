import type { AuthTokenResponse, AuthUserResponse } from "@midas/types";

export const AUTH_SESSION_STORAGE_KEY = "midas.auth.session";

export type AuthSession = {
  accessToken: string;
  user: AuthUserResponse;
};

export type StorageLike = Pick<Storage, "getItem" | "removeItem" | "setItem">;

export function toAuthSession(payload: AuthTokenResponse): AuthSession {
  return {
    accessToken: payload.access_token,
    user: payload.user,
  };
}

export function getBrowserStorage(): StorageLike | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage;
}

export function loadAuthSession(storage: StorageLike | null): AuthSession | null {
  const rawValue = storage?.getItem(AUTH_SESSION_STORAGE_KEY);
  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue) as AuthSession;
  } catch {
    return null;
  }
}

export function saveAuthSession(storage: StorageLike | null, session: AuthSession) {
  storage?.setItem(AUTH_SESSION_STORAGE_KEY, JSON.stringify(session));
}

export function clearAuthSession(storage: StorageLike | null) {
  storage?.removeItem(AUTH_SESSION_STORAGE_KEY);
}
