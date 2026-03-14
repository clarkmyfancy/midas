"use client";

import type { ClarificationTaskResponse } from "@midas/types";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { ApiError } from "../lib/api";
import { sendChatMessage } from "../lib/chat-client";
import { listClarifications, resolveClarification } from "../lib/review-api";
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
    "Start reflecting below. If a name or reference looks ambiguous, Midas will ask you here before it merges it into memory.",
};

export function ChatPageShell() {
  const router = useRouter();
  const aiPaneRef = useRef<HTMLDivElement | null>(null);
  const { isReady, session, logout } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [clarifications, setClarifications] = useState<ClarificationTaskResponse[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [resolvingTaskId, setResolvingTaskId] = useState<string | null>(null);

  useEffect(() => {
    if (isReady && !session) {
      router.replace("/login");
    }
  }, [isReady, router, session]);

  useEffect(() => {
    if (aiPaneRef.current) {
      aiPaneRef.current.scrollTop = aiPaneRef.current.scrollHeight;
    }
  }, [clarifications, messages]);

  async function loadClarifications() {
    if (!session) {
      return;
    }

    try {
      const response = await listClarifications(session.accessToken);
      setClarifications(response.tasks);
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load clarification prompts.");
    }
  }

  useEffect(() => {
    if (session) {
      void loadClarifications();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

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

    setMessages((currentMessages) => [
      ...currentMessages,
      userMessage,
      { id: assistantMessageId, role: "assistant", content: "", streaming: true },
    ]);
    setInput("");
    setError(null);
    setIsStreaming(true);

    try {
      await sendChatMessage({
        accessToken: session.accessToken,
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
        threadId: "dashboard-chat",
      });

      await loadClarifications();
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

  async function handleResolveClarification(
    taskId: string,
    resolution: "confirm_merge" | "keep_separate" | "dismiss",
  ) {
    if (!session) {
      return;
    }

    setResolvingTaskId(taskId);
    setError(null);
    try {
      await resolveClarification(session.accessToken, taskId, { resolution });
      await loadClarifications();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to resolve clarification.");
    } finally {
      setResolvingTaskId(null);
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

          {clarifications.map((task) => (
            <article
              className="reflect-message reflect-message-assistant reflect-clarification-message"
              key={task.id}
            >
              <div className="reflect-message-meta">
                <span>Midas</span>
              </div>
              <div className="reflect-message-body">
                <p>{task.prompt}</p>
                <p className="reflect-clarification-evidence">
                  Confidence {(task.confidence * 100).toFixed(0)}%. {task.evidence}
                </p>
              </div>
              <div className="review-clarification-actions">
                <button
                  className="button button-primary"
                  disabled={resolvingTaskId === task.id}
                  onClick={() => void handleResolveClarification(task.id, "confirm_merge")}
                  type="button"
                >
                  Yes, same
                </button>
                <button
                  className="button button-secondary"
                  disabled={resolvingTaskId === task.id}
                  onClick={() => void handleResolveClarification(task.id, "keep_separate")}
                  type="button"
                >
                  No, separate
                </button>
                <button
                  className="ghost-button"
                  disabled={resolvingTaskId === task.id}
                  onClick={() => void handleResolveClarification(task.id, "dismiss")}
                  type="button"
                >
                  Later
                </button>
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
                placeholder="Ask about what stood out, what repeated, or where you want clarity..."
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

          {error ? <div className="error-banner">{error}</div> : null}
        </form>
      </section>
    </main>
  );
}
