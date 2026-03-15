import { describe, expect, it } from "vitest";

import { toAuthSession } from "../lib/auth-session";

describe("auth session storage", () => {
  it("normalizes a token payload into an in-memory auth session shape", () => {
    expect(
      toAuthSession({
        access_token: "token-123",
        token_type: "bearer",
        user: { email: "user@example.com", id: "user-1", is_pro: false },
      }),
    ).toEqual({
      accessToken: "token-123",
      user: { email: "user@example.com", id: "user-1", is_pro: false },
    });
  });
});
