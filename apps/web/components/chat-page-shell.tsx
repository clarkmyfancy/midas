"use client";

import type {
  ChatMessageResponse,
  ChatThreadSummaryResponse,
  ClarificationTaskResponse,
} from "@midas/types";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { getChatThread, listChatThreads } from "../lib/chat-history";
import { ApiError } from "../lib/api";
import { sendChatMessage } from "../lib/chat-client";
import { listClarifications, resolveClarification } from "../lib/review-api";
import { useAuth } from "./auth-provider";


type LiveChatMessage = ChatMessageResponse & {
  streaming?: boolean;
};


function buildDraftThreadId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `thread-${Date.now()}`;
}


function formatHistoryTimestamp(value: string) {
  return new Date(value).toLocaleString([], {
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    month: "short",
  });
}


export function ChatPageShell() {
  const router = useRouter();
  const aiPaneRef = useRef<HTMLDivElement | null>(null);
  const { isReady, session, logout } = useAuth();
  const [threads, setThreads] = useState<ChatThreadSummaryResponse[]>([]);
  const [messages, setMessages] = useState<LiveChatMessage[]>([]);
  const [clarifications, setClarifications] = useState<ClarificationTaskResponse[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [draftThreadId, setDraftThreadId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [isThreadLoading, setIsThreadLoading] = useState(false);
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

  useEffect(() => {
    if (!success) {
      return;
    }
    const timeoutId = window.setTimeout(() => setSuccess(null), 4000);
    return () => window.clearTimeout(timeoutId);
  }, [success]);

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

  async function loadThread(threadId: string, persisted = false) {
    if (!session) {
      return;
    }

    const isPersistedThread = persisted || threads.some((thread) => thread.id === threadId);
    if (!isPersistedThread && draftThreadId === threadId) {
      setMessages([]);
      setSelectedThreadId(threadId);
      return;
    }

    setIsThreadLoading(true);
    try {
      const response = await getChatThread(session.accessToken, threadId);
      setMessages(response.messages);
      setSelectedThreadId(threadId);
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load chat thread.");
    } finally {
      setIsThreadLoading(false);
    }
  }

  async function loadThreads(preferredThreadId?: string) {
    if (!session) {
      return;
    }

    setIsHistoryLoading(true);
    try {
      const response = await listChatThreads(session.accessToken);
      const nextThreads = response.threads;
      setThreads(nextThreads);

      const nextThreadIds = new Set(nextThreads.map((thread) => thread.id));
      const selectedPersistedThreadId =
        preferredThreadId && nextThreadIds.has(preferredThreadId)
          ? preferredThreadId
          : selectedThreadId && nextThreadIds.has(selectedThreadId)
            ? selectedThreadId
            : nextThreads[0]?.id ?? null;

      if (selectedPersistedThreadId) {
        if (draftThreadId && draftThreadId === selectedPersistedThreadId) {
          setDraftThreadId(null);
        }
        await loadThread(selectedPersistedThreadId, true);
        return;
      }

      const nextDraftThreadId = preferredThreadId ?? draftThreadId ?? buildDraftThreadId();
      setDraftThreadId(nextDraftThreadId);
      setSelectedThreadId(nextDraftThreadId);
      setMessages([]);
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load chat history.");
    } finally {
      setIsHistoryLoading(false);
    }
  }

  useEffect(() => {
    if (session) {
      void loadClarifications();
      void loadThreads();
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

    const activeThreadId = selectedThreadId ?? draftThreadId ?? buildDraftThreadId();
    if (!selectedThreadId) {
      setSelectedThreadId(activeThreadId);
    }
    if (!draftThreadId && !threads.some((thread) => thread.id === activeThreadId)) {
      setDraftThreadId(activeThreadId);
    }

    const now = new Date().toISOString();
    const userMessage: LiveChatMessage = {
      id: `user-${Date.now()}`,
      thread_id: activeThreadId,
      role: "user",
      content: trimmedMessage,
      source_record_id: null,
      created_at: now,
    };
    const assistantMessageId = `assistant-${Date.now()}`;

    setMessages((currentMessages) => [
      ...currentMessages,
      userMessage,
      {
        id: assistantMessageId,
        thread_id: activeThreadId,
        role: "assistant",
        content: "",
        source_record_id: null,
        created_at: now,
        streaming: true,
      },
    ]);
    setInput("");
    setError(null);
    setSuccess(null);
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
        threadId: activeThreadId,
      });

      await loadClarifications();
      await loadThreads(activeThreadId);
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
    setSuccess(null);
    try {
      const response = await resolveClarification(session.accessToken, taskId, { resolution });
      await loadClarifications();
      if (selectedThreadId && threads.some((thread) => thread.id === selectedThreadId)) {
        await loadThread(selectedThreadId, true);
      }
      setSuccess(
        response.refresh_message ||
          "Clarification saved. Future memory extraction will use this resolution.",
      );
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to resolve clarification.");
    } finally {
      setResolvingTaskId(null);
    }
  }

  function handleSelectThread(threadId: string) {
    setError(null);
    setSuccess(null);
    void loadThread(threadId, true);
  }

  function handleNewChat() {
    const nextDraftThreadId = buildDraftThreadId();
    setDraftThreadId(nextDraftThreadId);
    setSelectedThreadId(nextDraftThreadId);
    setMessages([]);
    setInput("");
    setError(null);
    setSuccess(null);
  }

  const currentSourceRecordIds = new Set(
    messages
      .map((message) => message.source_record_id)
      .filter((value): value is string => Boolean(value)),
  );
  const visibleClarifications = clarifications.filter((task) => currentSourceRecordIds.has(task.source_record_id));

  return (
    <main className="page reflect-page">
      <section className="reflect-workspace reflect-workspace-history-open">
        <aside className={`reflect-history-sidebar ${isHistoryOpen ? "" : "reflect-history-sidebar-collapsed"}`}>
          <button
            aria-expanded={isHistoryOpen}
            className="reflect-history-toggle"
            onClick={() => setIsHistoryOpen((current) => !current)}
            type="button"
          >
            <span>{isHistoryOpen ? "Hide history" : "Threads"}</span>
            <span className="reflect-history-toggle-icon">{isHistoryOpen ? "←" : "→"}</span>
          </button>

          {isHistoryOpen ? (
            <div className="reflect-history-panel">
              <div className="reflect-history-header">
                <p className="eyebrow">Chat history</p>
                <p className="reflect-history-copy">
                  AI-generated thread titles. Pick a thread to load the full conversation with both your messages and Midas&apos;s replies.
                </p>
              </div>
              <div className="reflect-history-toolbar">
                <button className="button button-secondary" onClick={handleNewChat} type="button">
                  New chat
                </button>
              </div>
              <div className="reflect-history-list">
                {isHistoryLoading ? <div className="memory-empty">Loading threads...</div> : null}
                {!isHistoryLoading && !threads.length ? (
                  <div className="memory-empty">No saved threads yet. Start a new chat to create one.</div>
                ) : null}
                {!isHistoryLoading
                  ? threads.map((thread) => (
                      <button
                        className={[
                          "reflect-thread-button",
                          selectedThreadId === thread.id ? "reflect-thread-button-active" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        key={thread.id}
                        onClick={() => handleSelectThread(thread.id)}
                        type="button"
                      >
                        <div className="reflect-thread-row">
                          <strong>{thread.title}</strong>
                          <span>{formatHistoryTimestamp(thread.last_message_at)}</span>
                        </div>
                        <p>{thread.last_message_preview || "No preview yet."}</p>
                      </button>
                    ))
                  : null}
              </div>
            </div>
          ) : null}
        </aside>

        <section className="reflect-shell">
          <div className="reflect-ai-pane" ref={aiPaneRef}>
            <div className="reflect-status-row">
              <span className={`status-pill ${isStreaming ? "status-pill-live" : ""}`}>
                {isStreaming ? "Listening..." : isThreadLoading ? "Loading thread..." : "Ready"}
              </span>
            </div>

            {!messages.length && !isThreadLoading ? (
              <article className="reflect-message reflect-message-assistant">
                <div className="reflect-message-meta">
                  <span>Midas</span>
                </div>
                <div className="reflect-message-body">
                  Start reflecting below. If a name or reference looks ambiguous, Midas will ask you here before it merges it into memory.
                </div>
              </article>
            ) : null}

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

            {visibleClarifications.map((task) => (
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
            {success ? <div className="success-banner">{success}</div> : null}
          </form>
        </section>
      </section>
    </main>
  );
}
