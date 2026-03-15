"use client";

import type { WeeklyReviewResponse } from "@midas/types";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError } from "../lib/api";
import { getWeeklyReview, resolveClarification } from "../lib/review-api";
import { useAuth } from "./auth-provider";

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

export function ReviewPageShell() {
  const router = useRouter();
  const { isReady, logout, session } = useAuth();
  const [review, setReview] = useState<WeeklyReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [resolvingTaskId, setResolvingTaskId] = useState<string | null>(null);

  useEffect(() => {
    if (isReady && !session) {
      router.replace("/login");
    }
  }, [isReady, router, session]);

  async function loadReview() {
    if (!session) {
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const payload = await getWeeklyReview(session.accessToken, 7);
      setReview(payload);
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load the review.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (session) {
      void loadReview();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  useEffect(() => {
    if (!success) {
      return;
    }
    const timeoutId = window.setTimeout(() => setSuccess(null), 4000);
    return () => window.clearTimeout(timeoutId);
  }, [success]);

  async function handleResolve(taskId: string, resolution: "confirm_merge" | "keep_separate" | "dismiss") {
    if (!session) {
      return;
    }

    setResolvingTaskId(taskId);
    setError(null);
    setSuccess(null);
    try {
      const response = await resolveClarification(session.accessToken, taskId, { resolution });
      await loadReview();
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

  return (
    <main className="page review-page">
      <section className="review-hero panel">
        <p className="eyebrow">Review</p>
        <h1 className="review-title">Weekly reflection</h1>
        <p className="lede">
          This is the core weekly summary: your recent entries, stated goals, biometrics, and any clarifications
          that still need your input.
        </p>
        <div className="review-toolbar">
          <span className={`status-pill ${isLoading ? "status-pill-live" : ""}`}>
            {isLoading ? "Refreshing..." : "Ready"}
          </span>
          <button className="ghost-button" onClick={() => void loadReview()} type="button">
            Refresh
          </button>
        </div>
        {review ? <p className="review-summary">{review.summary}</p> : null}
        {error ? <div className="error-banner">{error}</div> : null}
        {success ? <div className="success-banner">{success}</div> : null}
      </section>

      <section className="review-stats-grid">
        {(review?.stats ?? []).map((stat) => (
          <article className="panel review-stat-card" key={stat.label}>
            <span className="review-stat-label">{stat.label}</span>
            <strong className="review-stat-value">{stat.value}</strong>
          </article>
        ))}
      </section>

      <section className="review-layout">
        <section className="panel review-findings-panel">
          <h2>Findings</h2>
          <div className="review-finding-list">
            {(review?.findings ?? []).map((finding) => (
              <article className="review-finding-card" key={finding.title}>
                <h3>{finding.title}</h3>
                <p>{finding.detail}</p>
                <ul className="bullet-list">
                  {finding.evidence.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section className="panel review-clarifications-panel">
          <h2>Clarifications</h2>
          <p>Resolve uncertain alias merges so future memory extraction gets sharper.</p>
          <div className="review-clarification-list">
            {(review?.clarifications ?? []).map((task) => (
              <article className="review-clarification-card" key={task.id}>
                <strong>{task.raw_name}</strong>
                <p>{task.prompt}</p>
                <span className="memory-small-copy">Confidence: {(task.confidence * 100).toFixed(0)}%</span>
                <span className="memory-small-copy">{task.evidence}</span>
                <div className="review-clarification-actions">
                  <button
                    className="button button-primary"
                    disabled={resolvingTaskId === task.id}
                    onClick={() => void handleResolve(task.id, "confirm_merge")}
                    type="button"
                  >
                    Merge
                  </button>
                  <button
                    className="button button-secondary"
                    disabled={resolvingTaskId === task.id}
                    onClick={() => void handleResolve(task.id, "keep_separate")}
                    type="button"
                  >
                    Keep Separate
                  </button>
                  <button
                    className="ghost-button"
                    disabled={resolvingTaskId === task.id}
                    onClick={() => void handleResolve(task.id, "dismiss")}
                    type="button"
                  >
                    Dismiss
                  </button>
                </div>
              </article>
            ))}
            {!review?.clarifications.length ? <div className="memory-empty">No pending clarifications.</div> : null}
          </div>
        </section>
      </section>

      <section className="panel review-entries-panel">
        <h2>Recent entries</h2>
        <div className="review-entry-list">
          {(review?.entries ?? []).map((entry) => (
            <article className="review-entry-card" key={entry.id}>
              <strong>{entry.journal_entry}</strong>
              <span>{formatDate(entry.created_at)}</span>
              <span>{entry.goals.join(", ") || "No explicit goals"}</span>
            </article>
          ))}
          {!review?.entries.length ? <div className="memory-empty">No entries in this review window yet.</div> : null}
        </div>
        {review?.warnings.length ? (
          <div className="review-warning-list">
            {review.warnings.map((warning) => (
              <div className="error-banner" key={warning}>
                {warning}
              </div>
            ))}
          </div>
        ) : null}
      </section>
    </main>
  );
}
