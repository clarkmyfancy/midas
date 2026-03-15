"use client";

import type {
  MemorySettingsResponse,
  JournalEntryResponse,
  MemoryDebugResponse,
  ProjectionJobResponse,
} from "@midas/types";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError } from "../lib/api";
import {
  deleteJournalEntry,
  createJournalEntry,
  getMemorySettings,
  getMemoryDebug,
  listJournalEntries,
  listProjectionJobs,
  runProjectionJobs,
} from "../lib/memory-api";
import { useAuth } from "./auth-provider";

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

export function MemoryPageShell() {
  const router = useRouter();
  const { isReady, logout, session } = useAuth();
  const [entries, setEntries] = useState<JournalEntryResponse[]>([]);
  const [jobs, setJobs] = useState<ProjectionJobResponse[]>([]);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [debugPayload, setDebugPayload] = useState<MemoryDebugResponse | null>(null);
  const [settings, setSettings] = useState<MemorySettingsResponse | null>(null);
  const [journalEntry, setJournalEntry] = useState(
    "I stayed up late for work, slept badly, and skipped my workout.",
  );
  const [goals, setGoals] = useState("Protect recovery, Exercise");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isReady && !session) {
      router.replace("/login");
    }
  }, [isReady, router, session]);

  async function refresh() {
    if (!session) {
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const [entryResponse, jobResponse] = await Promise.all([
        listJournalEntries(session.accessToken),
        listProjectionJobs(session.accessToken),
      ]);
      const settingsResponse = await getMemorySettings(session.accessToken);
      setEntries(entryResponse.entries);
      setJobs(jobResponse.projection_jobs);
      setSettings(settingsResponse);

      const nextEntryId = selectedEntryId ?? entryResponse.entries[0]?.id ?? null;
      setSelectedEntryId(nextEntryId);
      if (nextEntryId) {
        const debug = await getMemoryDebug(session.accessToken, nextEntryId);
        setDebugPayload(debug);
      } else {
        setDebugPayload(null);
      }
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(caughtError instanceof Error ? caughtError.message : "Failed to load memory inspector.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (session) {
      void refresh();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  async function handleCreateEntry() {
    if (!session) {
      return;
    }

    setError(null);
    setStatusMessage("Writing canonical journal entry...");
    try {
      const response = await createJournalEntry(session.accessToken, {
        journal_entry: journalEntry,
        goals: goals
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      });
      setSelectedEntryId(response.entry.id);
      if (settings?.auto_project_enabled) {
        setStatusMessage(`Created entry ${response.entry.id}. Waiting for automatic projections to finish...`);
        await waitForProjectionSettlement(response.entry.id);
      } else {
        setStatusMessage(`Created entry ${response.entry.id} and queued ${response.projection_jobs.length} jobs.`);
      }
      await refresh();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to create journal entry.");
    }
  }

  async function handleRunJobs() {
    if (!session) {
      return;
    }

    setError(null);
    setStatusMessage("Running pending projection jobs...");
    try {
      const result = await runProjectionJobs(session.accessToken, 20);
      setStatusMessage(
        `Claimed ${result.claimed_jobs} jobs, completed ${result.completed_jobs}, failed ${result.failed_jobs}.`,
      );
      await refresh();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to run projection jobs.");
    }
  }

  async function waitForProjectionSettlement(entryId: string) {
    if (!session) {
      return;
    }

    for (let attempt = 0; attempt < 8; attempt += 1) {
      const response = await listProjectionJobs(session.accessToken);
      const entryJobs = response.projection_jobs.filter((job) => job.source_record_id === entryId);
      setJobs(response.projection_jobs);
      if (entryJobs.length > 0 && entryJobs.every((job) => job.status !== "pending")) {
        setStatusMessage(
          `Automatic projections settled for ${entryId}: ${entryJobs.map((job) => `${job.projection_type}=${job.status}`).join(", ")}.`,
        );
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 350));
    }
    setStatusMessage(`Entry ${entryId} was created, but some automatic projections are still pending.`);
  }

  async function handleDeleteEntry() {
    if (!session || !selectedEntryId) {
      return;
    }

    setError(null);
    setStatusMessage(`Deleting ${selectedEntryId} and cleaning derived artifacts...`);
    try {
      const response = await deleteJournalEntry(session.accessToken, selectedEntryId);
      const cleanupSummary = response.cleanup
        .map((item) => `${item.store}=${item.success ? item.deleted_count : "error"}`)
        .join(", ");
      setSelectedEntryId(null);
      setDebugPayload(null);
      setStatusMessage(`Deleted ${response.entry_id}. Cleanup: ${cleanupSummary}.`);
      await refresh();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to delete journal entry.");
    }
  }

  async function handleSelectEntry(entryId: string) {
    if (!session) {
      return;
    }

    setSelectedEntryId(entryId);
    setError(null);
    try {
      const debug = await getMemoryDebug(session.accessToken, entryId);
      setDebugPayload(debug);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to load memory debug payload.");
    }
  }

  const selectedJobs = selectedEntryId
    ? jobs.filter((job) => job.source_record_id === selectedEntryId)
    : [];

  return (
    <main className="page memory-page">
      <section className="memory-grid">
        <section className="panel memory-compose-panel">
          <p className="eyebrow">Memory Dev</p>
          <h1>Projection inspector</h1>
          <p className="lede">
            Write journal entries into Postgres, run queued projections, then inspect the derived
            vector and graph artifacts locally.
          </p>
          <div className="memory-settings-chip">
            Auto project: {settings?.auto_project_enabled ? "on" : "off"}
          </div>
          <p className="memory-small-copy">
            Weaviate auto-run: {settings?.auto_project_weaviate_enabled ? "on" : "off"} | Neo4j auto-run:{" "}
            {settings?.auto_project_neo4j_enabled ? "on" : "off"}
          </p>

          <label className="label">
            Journal entry
            <textarea
              className="textarea memory-textarea"
              onChange={(event) => setJournalEntry(event.target.value)}
              value={journalEntry}
            />
          </label>

          <label className="label">
            Goals (comma separated)
            <input
              className="input"
              onChange={(event) => setGoals(event.target.value)}
              value={goals}
            />
          </label>

          <div className="memory-actions">
            <button className="button button-primary" onClick={handleCreateEntry} type="button">
              Create Entry
            </button>
            <button className="button button-secondary" onClick={handleRunJobs} type="button">
              Run Projections
            </button>
            <button
              className="button button-secondary"
              disabled={!selectedEntryId}
              onClick={handleDeleteEntry}
              type="button"
            >
              Delete Selected Entry
            </button>
            <button className="ghost-button" onClick={() => void refresh()} type="button">
              Refresh
            </button>
          </div>

          {statusMessage ? <div className="memory-status">{statusMessage}</div> : null}
          {error ? <div className="error-banner">{error}</div> : null}
        </section>

        <section className="panel memory-links-panel">
          <h2>Local services</h2>
          <p>Use these while the stack is running locally.</p>
          <p className="memory-small-copy">
            Current local mode: {settings?.auto_project_enabled ? "entries auto-project on write" : "manual projection run required"}
          </p>
          <p className="memory-small-copy">
            Automatic targets: {settings?.auto_project_weaviate_enabled ? "Weaviate on" : "Weaviate off"} /{" "}
            {settings?.auto_project_neo4j_enabled ? "Neo4j on" : "Neo4j off"}
          </p>
          <div className="memory-link-list">
            <a className="link-button" href="http://localhost:7474/browser/" rel="noreferrer" target="_blank">
              Open Neo4j Browser
            </a>
            <a className="link-button" href="http://localhost:8080/v1/schema" rel="noreferrer" target="_blank">
              Open Weaviate Schema
            </a>
            <a className="link-button" href="http://localhost:8080/v1/objects" rel="noreferrer" target="_blank">
              Open Weaviate Objects
            </a>
          </div>
          <p className="memory-small-copy">
            Neo4j default local auth: <code>neo4j / midasdevpassword</code>
          </p>
        </section>
      </section>

      <section className="memory-grid">
        <section className="panel memory-list-panel">
          <h2>Journal entries</h2>
          <p>{isLoading ? "Loading..." : `${entries.length} canonical entries stored.`}</p>
          <div className="memory-entry-list">
            {entries.map((entry) => (
              <button
                className={entry.id === selectedEntryId ? "memory-entry memory-entry-active" : "memory-entry"}
                key={entry.id}
                onClick={() => void handleSelectEntry(entry.id)}
                type="button"
              >
                <strong>{entry.journal_entry}</strong>
                <span>{formatDate(entry.created_at)}</span>
                <span>{entry.source}</span>
              </button>
            ))}
            {!entries.length ? <div className="memory-empty">No journal entries yet.</div> : null}
          </div>
        </section>

        <section className="panel memory-jobs-panel">
          <h2>Projection jobs</h2>
          <p>
            {selectedEntryId
              ? `${selectedJobs.length} jobs for the selected entry.`
              : `${jobs.length} jobs queued for this user.`}
          </p>
          <div className="memory-job-list">
            {(selectedEntryId ? selectedJobs : jobs).map((job) => (
              <article className="memory-job-card" key={job.id}>
                <strong>{job.projection_type}</strong>
                <span className={`memory-job-status memory-job-status-${job.status}`}>{job.status}</span>
                <span>Attempts: {job.attempts}</span>
                {job.last_error ? <span className="memory-job-error">{job.last_error}</span> : null}
              </article>
            ))}
          </div>
        </section>
      </section>

      <section className="panel memory-debug-panel">
        <h2>Debug payload</h2>
        <p>
          Inspect the canonical record, derived Weaviate objects, and the Neo4j observation
          subgraph for the selected entry.
        </p>
        <pre className="memory-pre">
          {JSON.stringify(debugPayload, null, 2) || "Select an entry to inspect."}
        </pre>
      </section>
    </main>
  );
}
