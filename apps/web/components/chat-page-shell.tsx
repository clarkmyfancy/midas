"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { ApiError } from "../lib/api";
import { sendChatMessage } from "../lib/chat-client";
import { useAuth } from "./auth-provider";

type ChatRole = "assistant" | "user";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  streaming?: boolean;
};

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Send a reflection note here and Midas will stream the current LLM output into this conversation live.",
};

export function ChatPageShell() {
  const router = useRouter();
  const streamRef = useRef<HTMLDivElement | null>(null);
  const { isReady, session, logout } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [steps, setSteps] = useState("");
  const [sleepHours, setSleepHours] = useState("");
  const [hrvMs, setHrvMs] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    if (isReady && !session) {
      router.replace("/login");
    }
  }, [isReady, router, session]);

  useEffect(() => {
    if (streamRef.current) {
      streamRef.current.scrollTop = streamRef.current.scrollHeight;
    }
  }, [messages]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!session || isStreaming) {
      return;
    }

    const trimmedMessage = input.trim();
    if (!trimmedMessage) {
      return;
    }

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmedMessage,
    };
    const assistantMessageId = `assistant-${Date.now()}`;
    const nextMessages = [
      ...messages,
      userMessage,
      { id: assistantMessageId, role: "assistant" as const, content: "", streaming: true },
    ];

    setMessages(nextMessages);
    setInput("");
    setError(null);
    setIsStreaming(true);

    try {
      await sendChatMessage({
        accessToken: session.accessToken,
        hrvMs: hrvMs.trim() ? Number(hrvMs) : null,
        journalEntry: trimmedMessage,
        onToken(token) {
          setMessages((currentMessages) =>
            currentMessages.map((message) =>
              message.id === assistantMessageId
                ? {
                    ...message,
                    content: `${message.content}${token}`,
                  }
                : message,
            ),
          );
        },
        sleepHours: sleepHours.trim() ? Number(sleepHours) : null,
        steps: steps.trim() ? Number(steps) : null,
        threadId: "dashboard-chat",
      });

      setMessages((currentMessages) =>
        currentMessages.map((message) =>
          message.id === assistantMessageId ? { ...message, streaming: false } : message,
        ),
      );
    } catch (caughtError) {
      setMessages((currentMessages) =>
        currentMessages.map((message) =>
          message.id === assistantMessageId
            ? {
                ...message,
                content:
                  message.content ||
                  "The backend did not return a usable stream for this message.",
                streaming: false,
              }
            : message,
        ),
      );

      if (caughtError instanceof ApiError) {
        setError(caughtError.message);
        if (caughtError.status === 401) {
          logout();
          router.replace("/login");
        }
      } else {
        setError("Unable to reach the chat backend.");
      }
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <main className="page chat-layout">
      <section className="chat-shell">
        <div className="panel">
          <div className="chat-toolbar">
            <div>
              <p className="eyebrow">Chat</p>
              <h1>Live reflection stream</h1>
            </div>
            <span className={`status-pill ${isStreaming ? "status-pill-live" : ""}`}>
              {isStreaming ? "Streaming tokens" : "Ready"}
            </span>
          </div>
          <p className="lede">
            Messages here are sent to the authenticated backend endpoint and rendered as
            SSE tokens arrive.
          </p>
        </div>

        <div className="panel chat-stream" ref={streamRef}>
          {messages.map((message) => (
            <article
              className={[
                "chat-message",
                message.role === "user" ? "chat-message-user" : "chat-message-assistant",
                message.streaming ? "chat-message-streaming" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              key={message.id}
            >
              <div className="message-meta">
                <span>{message.role === "user" ? "You" : "Midas"}</span>
                {message.streaming ? <span className="status-dot">Live</span> : null}
              </div>
              <div className="message-body">
                {message.content || "Waiting for the first token..."}
              </div>
            </article>
          ))}
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <div className="composer-grid">
            <label className="label">
              Reflection prompt
              <textarea
                className="textarea"
                onChange={(event) => setInput(event.target.value)}
                placeholder="I felt focused in the morning, then my energy dropped and I pushed through anyway."
                value={input}
              />
            </label>

            <div className="composer-inline">
              <label className="label">
                Steps
                <input
                  className="input"
                  inputMode="numeric"
                  onChange={(event) => setSteps(event.target.value)}
                  placeholder="6840"
                  value={steps}
                />
              </label>

              <label className="label">
                Sleep hours
                <input
                  className="input"
                  inputMode="decimal"
                  onChange={(event) => setSleepHours(event.target.value)}
                  placeholder="6.5"
                  value={sleepHours}
                />
              </label>

              <label className="label">
                HRV (ms)
                <input
                  className="input"
                  inputMode="decimal"
                  onChange={(event) => setHrvMs(event.target.value)}
                  placeholder="42"
                  value={hrvMs}
                />
              </label>
            </div>
          </div>

          {error ? <div className="error-banner">{error}</div> : null}

          <div className="composer-actions">
            <button className="button button-primary" disabled={isStreaming || !session} type="submit">
              {isStreaming ? "Streaming..." : "Send to Midas"}
            </button>
            <p className="hint">
              Signed in as <strong>{session?.user.email ?? "unknown"}</strong>
            </p>
          </div>
        </form>
      </section>

      <aside className="panel chat-sidebar">
        <p className="eyebrow">Session</p>
        <h2>What this page is doing</h2>
        <ul className="stat-list">
          <li>Uses your bearer token from the login flow.</li>
          <li>Sends requests to `/api/v1/reflections` on the FastAPI backend.</li>
          <li>Consumes `text/event-stream` and appends each `data:` token live.</li>
          <li>Uses a stable `dashboard-chat` thread per authenticated user.</li>
        </ul>
      </aside>
    </main>
  );
}
