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
    "Start reflecting below. Your response will stream into this upper pane as Midas produces it.",
};

export function ChatPageShell() {
  const router = useRouter();
  const aiPaneRef = useRef<HTMLDivElement | null>(null);
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
    if (aiPaneRef.current) {
      aiPaneRef.current.scrollTop = aiPaneRef.current.scrollHeight;
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
    <main className="page reflect-page">
      <section className="reflect-shell">
        <div className="reflect-ai-pane" ref={aiPaneRef}>
          <div className="reflect-status-row">
            <span className={`status-pill ${isStreaming ? "status-pill-live" : ""}`}>
              {isStreaming ? "Listening..." : "Ready"}
            </span>
          </div>

          {messages.map((message) => (
            <article
              className={[
                "reflect-message",
                message.role === "user" ? "reflect-message-user" : "reflect-message-assistant",
                message.streaming ? "reflect-message-streaming" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              key={message.id}
            >
              <div className="reflect-message-meta">
                <span>{message.role === "user" ? "You" : "Midas"}</span>
              </div>
              <div className="reflect-message-body">
                {message.content || "Waiting for the first token..."}
              </div>
            </article>
          ))}
        </div>

        <form className="reflect-composer" onSubmit={handleSubmit}>
          <label className="reflect-composer-label">
            Reflection
            <div className="reflect-input-shell">
              <textarea
                className="reflect-textarea"
                onChange={(event) => setInput(event.target.value)}
                placeholder="Ask a question about your reflection..."
                value={input}
              />
              <button
                aria-label="Send reflection"
                className="reflect-send-button"
                disabled={isStreaming || !session}
                type="submit"
              >
                ↑
              </button>
            </div>
          </label>

          <div className="reflect-metrics-row">
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

          {error ? <div className="error-banner">{error}</div> : null}
        </form>
      </section>
    </main>
  );
}
