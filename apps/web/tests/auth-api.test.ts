import { describe, expect, it, vi } from "vitest";

import {
  deleteAccountData,
  getCurrentUser,
  loginWithApi,
  registerWithApi,
  wipeLocalData,
} from "../lib/auth-api";

describe("auth api", () => {
  it("registers through the backend auth endpoint", async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("http://127.0.0.1:8000/api/v1/auth/register");
      expect(init?.method).toBe("POST");

      return new Response(
        JSON.stringify({
          access_token: "token-abc",
          token_type: "bearer",
          user: { email: "user@example.com", id: "user-1", is_pro: false },
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      );
    });

    const session = await registerWithApi(
      { email: "user@example.com", password: "supersecret" },
      fetcher as typeof fetch,
    );

    expect(session.accessToken).toBe("token-abc");
    expect(session.user.email).toBe("user@example.com");
  });

  it("logs in and returns a normalized auth session", async () => {
    const fetcher = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          access_token: "token-login",
          token_type: "bearer",
          user: { email: "user@example.com", id: "user-1", is_pro: false },
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      );
    });

    const session = await loginWithApi(
      { email: "user@example.com", password: "supersecret" },
      fetcher as typeof fetch,
    );

    expect(session).toEqual({
      accessToken: "token-login",
      user: { email: "user@example.com", id: "user-1", is_pro: false },
    });
  });

  it("loads the current user with the bearer token", async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.headers).toEqual({
        Accept: "application/json",
        Authorization: "Bearer token-123",
      });

      return new Response(
        JSON.stringify({ email: "user@example.com", id: "user-1", is_pro: false }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      );
    });

    const user = await getCurrentUser("token-123", fetcher as typeof fetch);

    expect(user.email).toBe("user@example.com");
  });

  it("deletes account data with the bearer token", async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe("DELETE");
      expect(init?.headers).toEqual({
        Accept: "application/json",
        Authorization: "Bearer token-123",
      });

      return new Response(
        JSON.stringify({
          user_id: "user-1",
          cleanup: [
            { store: "postgres", success: true, deleted_count: 8 },
            { store: "weaviate", success: true, deleted_count: 6 },
            { store: "neo4j", success: true, deleted_count: 5 },
          ],
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      );
    });

    const response = await deleteAccountData("token-123", fetcher as typeof fetch);

    expect(response.user_id).toBe("user-1");
    expect(response.cleanup.map((item) => item.store)).toEqual(["postgres", "weaviate", "neo4j"]);
  });

  it("wipes local data through the dev endpoint", async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe("DELETE");
      expect(init?.headers).toEqual({
        Accept: "application/json",
        Authorization: "Bearer token-123",
      });

      return new Response(
        JSON.stringify({
          cleanup: [
            { store: "postgres", success: true, deleted_count: 8 },
            { store: "weaviate", success: true, deleted_count: 1, details: { deleted_class: true } },
            { store: "neo4j", success: true, deleted_count: 6 },
          ],
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      );
    });

    const response = await wipeLocalData("token-123", fetcher as typeof fetch);

    expect(response.cleanup.map((item) => item.store)).toEqual(["postgres", "weaviate", "neo4j"]);
  });
});
