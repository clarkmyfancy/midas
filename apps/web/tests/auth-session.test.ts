import { describe, expect, it } from "vitest";

import {
  AUTH_REFRESH_TOKEN_STORAGE_KEY,
  clearRefreshToken,
  loadRefreshToken,
  saveRefreshToken,
  toAuthSession,
  type StorageLike,
} from "../lib/auth-session";

function createMemoryStorage(): StorageLike {
  const values = new Map<string, string>();

  return {
    getItem(key) {
      return values.get(key) ?? null;
    },
    removeItem(key) {
      values.delete(key);
    },
    setItem(key, value) {
      values.set(key, value);
    },
  };
}

describe("auth session storage", () => {
  it("normalizes a token payload into an in-memory auth session shape", () => {
    expect(
      toAuthSession({
        access_token: "token-123",
        refresh_token: "refresh-123",
        token_type: "bearer",
        user: { email: "user@example.com", id: "user-1", is_pro: false },
      }),
    ).toEqual({
      accessToken: "token-123",
      refreshToken: "refresh-123",
      user: { email: "user@example.com", id: "user-1", is_pro: false },
    });
  });

  it("persists only the refresh token for silent restore", () => {
    const storage = createMemoryStorage();

    saveRefreshToken(storage, "refresh-abc");

    expect(loadRefreshToken(storage)).toBe("refresh-abc");
    expect(storage.getItem(AUTH_REFRESH_TOKEN_STORAGE_KEY)).toBe("refresh-abc");
    clearRefreshToken(storage);
    expect(loadRefreshToken(storage)).toBeNull();
  });
});
