import type {
  JournalDeleteResponse,
  JournalEntryCreateRequest,
  JournalEntryListResponse,
  JournalIngestResponse,
  MemorySettingsResponse,
  MemoryDebugResponse,
  ProjectionJobListResponse,
  ProjectionRunResponse,
} from "@midas/types";

import { requestJson } from "./api";

function authHeaders(accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
  };
}

export function listJournalEntries(accessToken: string, fetcher: typeof fetch = fetch) {
  return requestJson<JournalEntryListResponse>(
    "/api/v1/journal-entries",
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      method: "GET",
    },
    fetcher,
  );
}

export function listProjectionJobs(accessToken: string, fetcher: typeof fetch = fetch) {
  return requestJson<ProjectionJobListResponse>(
    "/api/v1/projection-jobs",
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      method: "GET",
    },
    fetcher,
  );
}

export function getMemorySettings(accessToken: string, fetcher: typeof fetch = fetch) {
  return requestJson<MemorySettingsResponse>(
    "/api/v1/memory/settings",
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      method: "GET",
    },
    fetcher,
  );
}

export function createJournalEntry(
  accessToken: string,
  payload: JournalEntryCreateRequest,
  fetcher: typeof fetch = fetch,
) {
  return requestJson<JournalIngestResponse>(
    "/api/v1/journal-entries",
    {
      body: JSON.stringify(payload),
      headers: authHeaders(accessToken),
      method: "POST",
    },
    fetcher,
  );
}

export function runProjectionJobs(
  accessToken: string,
  limit = 20,
  fetcher: typeof fetch = fetch,
) {
  return requestJson<ProjectionRunResponse>(
    `/api/v1/projection-jobs/run?limit=${limit}`,
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      method: "POST",
    },
    fetcher,
  );
}

export function getMemoryDebug(
  accessToken: string,
  entryId: string,
  fetcher: typeof fetch = fetch,
) {
  return requestJson<MemoryDebugResponse>(
    `/api/v1/journal-entries/${entryId}/debug`,
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      method: "GET",
    },
    fetcher,
  );
}

export function deleteJournalEntry(
  accessToken: string,
  entryId: string,
  fetcher: typeof fetch = fetch,
) {
  return requestJson<JournalDeleteResponse>(
    `/api/v1/journal-entries/${entryId}`,
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      method: "DELETE",
    },
    fetcher,
  );
}
