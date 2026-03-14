"use client";

import type { GraphNodeResponse, GraphRelationshipResponse, WeeklyReviewResponse } from "@midas/types";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError } from "../lib/api";
import { getWeeklyReview, resolveClarification } from "../lib/review-api";
import { useAuth } from "./auth-provider";

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function displayGraphNode(node: GraphNodeResponse) {
  return (
    String(node.properties.display_name || node.properties.canonical_name || node.properties.summary || node.node_id)
  );
}

function relationshipLabel(relationship: GraphRelationshipResponse) {
  return relationship.type.toLowerCase().replaceAll("_", " ");
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
      await resolveClarification(session.accessToken, taskId, { resolution });
      await loadReview();
      setSuccess("Memory refreshed. Neo4j and Weaviate were updated for this entry.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to resolve clarification.");
    } finally {
      setResolvingTaskId(null);
    }
  }

  const graphNodes = review?.graph.nodes.filter((node) => !node.labels.includes("Observation")) ?? [];
  const graphRelationships = review?.graph.relationships.filter((relationship) => relationship.type !== "OBSERVED") ?? [];

  return (
    <main className="page review-page">
      <section className="review-hero panel">
        <p className="eyebrow">Review</p>
        <h1 className="review-title">Weekly memory review</h1>
        <p className="lede">
          This page is the hybrid Phase 4 view: canonical journal entries, Weaviate memory artifacts,
          Neo4j graph structure, and pending clarification tasks in one place.
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
          <p>Resolve uncertain alias merges so future graph extraction gets sharper.</p>
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

      <section className="review-layout">
        <section className="panel review-memory-panel">
          <h2>Memory highlights</h2>
          <div className="review-memory-list">
            {(review?.memory_highlights ?? []).map((artifact) => (
              <article className="review-memory-card" key={artifact.object_id}>
                <strong>{artifact.class_name || "MemoryArtifact"}</strong>
                <p>{artifact.content || "No content available."}</p>
                <span className="memory-small-copy">{artifact.url}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="panel review-graph-panel">
          <h2>Graph snapshot</h2>
          <div className="review-graph-grid">
            <div className="review-graph-column">
              <h3>Entities</h3>
              <div className="review-entity-list">
                {graphNodes.map((node) => (
                  <article className="review-entity-card" key={node.node_id}>
                    <strong>{displayGraphNode(node)}</strong>
                    <span>{node.labels.join(", ")}</span>
                  </article>
                ))}
              </div>
            </div>
            <div className="review-graph-column">
              <h3>Relationships</h3>
              <div className="review-relationship-list">
                {graphRelationships.map((relationship) => (
                  <article className="review-relationship-card" key={relationship.relationship_id}>
                    <strong>{relationshipLabel(relationship)}</strong>
                    <span>{relationship.properties.evidence ? String(relationship.properties.evidence) : "Derived graph relation"}</span>
                  </article>
                ))}
              </div>
            </div>
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
