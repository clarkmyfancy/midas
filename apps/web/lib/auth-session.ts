import type { AuthTokenResponse, AuthUserResponse } from "@midas/types";

export type AuthSession = {
  accessToken: string;
  user: AuthUserResponse;
};

export function toAuthSession(payload: AuthTokenResponse): AuthSession {
  return {
    accessToken: payload.access_token,
    user: payload.user,
  };
}
