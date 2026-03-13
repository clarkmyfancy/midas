import { describe, expect, it } from "vitest";

import {
  AUTH_SESSION_STORAGE_KEY,
  clearAuthSession,
  loadAuthSession,
  saveAuthSession,
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
  it("saves and reloads a login session", () => {
    const storage = createMemoryStorage();
    const session = toAuthSession({
      access_token: "token-123",
      token_type: "bearer",
      user: { email: "user@example.com", id: "user-1", is_pro: false },
    });

    saveAuthSession(storage, session);

    expect(loadAuthSession(storage)).toEqual(session);
    expect(storage.getItem(AUTH_SESSION_STORAGE_KEY)).toContain("token-123");
  });

  it("clears the stored session on logout", () => {
    const storage = createMemoryStorage();
    saveAuthSession(storage, {
      accessToken: "token-123",
      user: { email: "user@example.com", id: "user-1", is_pro: false },
    });

    clearAuthSession(storage);

    expect(loadAuthSession(storage)).toBeNull();
  });
});
