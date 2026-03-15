"use client";

import type { InsightCardResponse, InsightsResponse } from "@midas/types";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError } from "../lib/api";
import { getInsights } from "../lib/insights-api";
import { useAuth } from "./auth-provider";

const WINDOW_OPTIONS = [
  { label: "14 days", value: 14 },
  { label: "30 days", value: 30 },
  { label: "60 days", value: 60 },
] as const;

const CONFIDENCE_OPTIONS = [
  { label: "Medium+", value: 0.65 },
  { label: "High only", value: 0.85 },
  { label: "All", value: 0 },
] as const;

function sourceLabel(card: InsightCardResponse) {
  return card.source_types.join(" + ");
}

export function InsightsPageShell() {
  const router = useRouter();
  const { isReady, logout, session } = useAuth();
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [windowDays, setWindowDays] = useState<number>(30);
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.65);

  useEffect(() => {
    if (isReady && !session) {
      router.replace("/login");
    }
  }, [isReady, router, session]);

  async function loadInsights(currentWindowDays = windowDays, currentThreshold = confidenceThreshold) {
    if (!session) {
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const payload = await getInsights(session.accessToken, currentWindowDays, currentThreshold);
      setInsights(payload);
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load insights.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (session) {
      void loadInsights(windowDays, confidenceThreshold);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, windowDays, confidenceThreshold]);

  return (
    <main className="page insights-page">
      <section className="insights-hero panel">
        <p className="eyebrow">Insights</p>
        <h1 className="review-title">Longitudinal interpretation</h1>
        <p className="lede">
          This page synthesizes the longer-running story across your entries, memory summaries, and graph links,
          so the output is about patterns and structure rather than raw memory inspection.
        </p>
        <div className="review-toolbar insights-toolbar">
          <label className="review-filter">
            <span>Window</span>
            <select
              className="input review-filter-select"
              onChange={(event) => setWindowDays(Number(event.target.value))}
              value={windowDays}
            >
              {WINDOW_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="review-filter">
            <span>Confidence</span>
            <select
              className="input review-filter-select"
              onChange={(event) => setConfidenceThreshold(Number(event.target.value))}
              value={confidenceThreshold}
            >
              {CONFIDENCE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button className="ghost-button" onClick={() => void loadInsights(windowDays, confidenceThreshold)} type="button">
            {isLoading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
        {insights ? <p className="review-summary">{insights.summary}</p> : null}
        {error ? <div className="error-banner">{error}</div> : null}
      </section>

      <section className="review-stats-grid insights-stats-grid">
        {(insights?.stats ?? []).map((stat) => (
          <article className="panel review-stat-card" key={stat.label}>
            <span className="review-stat-label">{stat.label}</span>
            <strong className="review-stat-value">{stat.value}</strong>
          </article>
        ))}
      </section>

      <section className="insights-section-list">
        {(insights?.sections ?? []).map((section) => (
          <section className="panel insights-section-panel" key={section.id}>
            <div className="insights-section-header">
              <div>
                <p className="eyebrow">{section.title}</p>
                <h2>{section.title}</h2>
              </div>
              <p className="insights-section-description">{section.description}</p>
            </div>
            <div className="insights-card-grid">
              {section.cards.map((card) => (
                <article className={`insight-card insight-card-${card.severity}`} key={card.id}>
                  <div className="insight-card-header">
                    <strong>{card.title}</strong>
                    <span className={`review-badge review-badge-${card.severity}`}>{card.severity}</span>
                  </div>
                  <p className="insight-card-summary">{card.summary}</p>
                  <div className="insight-card-meta">
                    <span className="review-badge review-badge-unknown">{Math.round(card.confidence * 100)}%</span>
                    <span className="review-badge review-badge-normalized">{sourceLabel(card)}</span>
                  </div>
                  {card.related_entities.length ? (
                    <div className="insight-entity-row">
                      {card.related_entities.map((entity) => (
                        <span className="insight-entity-chip" key={entity}>
                          {entity}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <ul className="bullet-list">
                    {card.evidence.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </section>
        ))}
      </section>

      {insights?.warnings.length ? (
        <section className="panel review-entries-panel">
          <h2>Warnings</h2>
          <div className="review-warning-list">
            {insights.warnings.map((warning) => (
              <div className="error-banner" key={warning}>
                {warning}
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}
