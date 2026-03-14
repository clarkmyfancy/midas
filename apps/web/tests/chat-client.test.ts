import { describe, expect, it, vi } from "vitest";

import { drainSseBuffer, sendChatMessage } from "../lib/chat-client";

function createStreamingResponse(chunks: string[]) {
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(new TextEncoder().encode(chunk));
      }
      controller.close();
    },
  });

  return new Response(stream, {
    headers: { "Content-Type": "text/event-stream" },
    status: 200,
  });
}

describe("chat client", () => {
  it("parses SSE frames while preserving trailing partial chunks", () => {
    expect(drainSseBuffer("data: hello\n\ndata: wor")).toEqual({
      rest: "data: wor",
      tokens: ["hello"],
    });
  });

  it("preserves leading spaces inside streamed tokens", () => {
    expect(drainSseBuffer("data:  reports\n\n")).toEqual({
      rest: "",
      tokens: [" reports"],
    });
  });

  it("posts the reflection request and streams tokens in order", async () => {
    const onToken = vi.fn();
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("http://127.0.0.1:8000/api/v1/reflections");
      expect(init?.method).toBe("POST");
      expect(init?.headers).toEqual({
        Authorization: "Bearer token-123",
        "Content-Type": "application/json",
      });

      expect(init?.body).toBe(
        JSON.stringify({
          goals: [],
          journal_entry: "I said I was fine but I was exhausted.",
          thread_id: "dashboard-chat",
        }),
      );

      return createStreamingResponse([
        "data: - Semantic drift:\n\n",
        "data: low recovery\n\n",
      ]);
    });

    await sendChatMessage(
      {
        accessToken: "token-123",
        journalEntry: "I said I was fine but I was exhausted.",
        onToken,
        threadId: "dashboard-chat",
      },
      fetcher as typeof fetch,
    );

    expect(onToken).toHaveBeenNthCalledWith(1, "- Semantic drift:");
    expect(onToken).toHaveBeenNthCalledWith(2, "low recovery");
  });
});
