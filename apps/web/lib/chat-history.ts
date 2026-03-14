import type { ChatThreadDetailResponse, ChatThreadListResponse } from "@midas/types";

import { requestJson } from "./api";


export function listChatThreads(accessToken: string, fetcher: typeof fetch = fetch) {
  return requestJson<ChatThreadListResponse>(
    "/api/v1/chat/threads",
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      method: "GET",
    },
    fetcher,
  );
}


export function getChatThread(
  accessToken: string,
  threadId: string,
  fetcher: typeof fetch = fetch,
) {
  return requestJson<ChatThreadDetailResponse>(
    `/api/v1/chat/threads/${threadId}`,
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      method: "GET",
    },
    fetcher,
  );
}
