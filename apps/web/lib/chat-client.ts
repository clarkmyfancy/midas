import { ApiError, resolveApiUrl } from "./api";

export function drainSseBuffer(buffer: string) {
  const frames = buffer.split("\n\n");
  const rest = frames.pop() || "";
  const tokens: string[] = [];

  for (const frame of frames) {
    const payload = frame
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => (line.startsWith("data: ") ? line.slice(6) : line.slice(5)))
      .join("\n");

    if (payload) {
      tokens.push(payload);
    }
  }

  return { rest, tokens };
}

export async function streamSseTokens(
  response: Response,
  onToken: (token: string) => void,
) {
  if (!response.ok) {
    const message = await response.text();
    throw new ApiError(message || "Streaming request failed.", response.status);
  }

  if (!response.body) {
    throw new ApiError("Streaming response body was empty.", response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parsed = drainSseBuffer(buffer);
    buffer = parsed.rest;
    parsed.tokens.forEach((token) => onToken(token));
  }

  buffer += decoder.decode();
  const finalChunk = drainSseBuffer(`${buffer}\n\n`);
  finalChunk.tokens.forEach((token) => onToken(token));
}

type SendChatMessageParams = {
  accessToken: string;
  hrvMs: number | null;
  journalEntry: string;
  onToken: (token: string) => void;
  sleepHours: number | null;
  steps: number | null;
  threadId: string;
};

export async function sendChatMessage(
  {
    accessToken,
    hrvMs,
    journalEntry,
    onToken,
    sleepHours,
    steps,
    threadId,
  }: SendChatMessageParams,
  fetcher: typeof fetch = fetch,
) {
  const response = await fetcher(resolveApiUrl("/api/v1/reflections"), {
    body: JSON.stringify({
      goals: [],
      hrv_ms: hrvMs,
      journal_entry: journalEntry,
      sleep_hours: sleepHours,
      steps,
      thread_id: threadId,
    }),
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    method: "POST",
  });

  await streamSseTokens(response, onToken);
}
