import type { InsightsResponse } from "@midas/types";

import { requestJson } from "./api";

export function getInsights(
  accessToken: string,
  windowDays = 30,
  confidenceThreshold = 0.65,
  fetcher: typeof fetch = fetch,
) {
  return requestJson<InsightsResponse>(
    `/api/v1/insights?window_days=${windowDays}&confidence_threshold=${confidenceThreshold}`,
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      method: "GET",
    },
    fetcher,
  );
}
