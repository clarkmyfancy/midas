import type {
  ClarificationResolveRequest,
  ClarificationTaskResponse,
  WeeklyReviewResponse,
} from "@midas/types";

import { requestJson } from "./api";

export function getWeeklyReview(
  accessToken: string,
  windowDays = 7,
  fetcher: typeof fetch = fetch,
) {
  return requestJson<WeeklyReviewResponse>(
    `/api/v1/review?window_days=${windowDays}`,
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      method: "GET",
    },
    fetcher,
  );
}

export function resolveClarification(
  accessToken: string,
  taskId: string,
  payload: ClarificationResolveRequest,
  fetcher: typeof fetch = fetch,
) {
  return requestJson<ClarificationTaskResponse>(
    `/api/v1/clarifications/${taskId}/resolve`,
    {
      body: JSON.stringify(payload),
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      method: "POST",
    },
    fetcher,
  );
}
