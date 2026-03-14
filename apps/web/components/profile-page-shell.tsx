"use client";

import type { DerivedStoreCleanupResponse } from "@midas/types";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError } from "../lib/api";
import { deleteAccountData, wipeLocalData } from "../lib/auth-api";
import { useAuth } from "./auth-provider";

function deriveUsername(email: string) {
  return email.split("@")[0] || email;
}

function summarizeCleanup(cleanup: DerivedStoreCleanupResponse[]) {
  return cleanup.map((item) => `${item.store}=${item.success ? item.deleted_count : "error"}`).join(", ");
}

export function ProfilePageShell() {
  const router = useRouter();
  const { isReady, logout, session } = useAuth();
  const isDevelopment = process.env.NODE_ENV !== "production";
  const [activeSection, setActiveSection] = useState<"profile" | "data">("profile");
  const [cleanup, setCleanup] = useState<DerivedStoreCleanupResponse[]>([]);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDeletingData, setIsDeletingData] = useState(false);
  const [isWipingLocalData, setIsWipingLocalData] = useState(false);

  useEffect(() => {
    if (isReady && !session) {
      router.replace("/login");
    }
  }, [isReady, router, session]);

  const email = session?.user.email ?? "account@example.com";
  const username = deriveUsername(email);

  function handleLogout() {
    logout();
    router.push("/login");
  }

  async function handleDeleteData() {
    if (!session || isDeletingData || isWipingLocalData) {
      return;
    }

    const shouldDelete = window.confirm(
      "Delete all journal, vector, and graph data for this account? Your account will stay active.",
    );
    if (!shouldDelete) {
      return;
    }

    setIsDeletingData(true);
    setError(null);
    setStatusMessage("Deleting account data from Postgres, Weaviate, and Neo4j...");
    try {
      const response = await deleteAccountData(session.accessToken);
      setCleanup(response.cleanup);
      setStatusMessage(`Deleted account data. Cleanup: ${summarizeCleanup(response.cleanup)}.`);
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(caughtError instanceof Error ? caughtError.message : "Failed to delete account data.");
    } finally {
      setIsDeletingData(false);
    }
  }

  async function handleWipeLocalData() {
    if (!session || isDeletingData || isWipingLocalData) {
      return;
    }

    const shouldDelete = window.confirm(
      "Delete all local Midas memory data for every account on this environment? User accounts will stay active.",
    );
    if (!shouldDelete) {
      return;
    }

    setIsWipingLocalData(true);
    setError(null);
    setStatusMessage("Wiping all local memory data from Postgres, Weaviate, and Neo4j...");
    try {
      const response = await wipeLocalData(session.accessToken);
      setCleanup(response.cleanup);
      setStatusMessage(`Wiped local memory data. Cleanup: ${summarizeCleanup(response.cleanup)}.`);
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(caughtError instanceof Error ? caughtError.message : "Failed to wipe local data.");
    } finally {
      setIsWipingLocalData(false);
    }
  }

  return (
    <main className="page profile-page">
      <section className="profile-layout">
        <aside className="profile-sidebar">
          <p className="profile-kicker">Settings</p>
          <h1 className="profile-sidebar-title">Profile</h1>
          <p className="profile-sidebar-copy">
            Review your account and manage what you want to export or delete.
          </p>

          <div className="profile-sidebar-nav">
            <button
              className={activeSection === "profile" ? "profile-sidebar-link profile-sidebar-link-active" : "profile-sidebar-link"}
              onClick={() => setActiveSection("profile")}
              type="button"
            >
              Profile
            </button>
            <button
              className={activeSection === "data" ? "profile-sidebar-link profile-sidebar-link-active" : "profile-sidebar-link"}
              onClick={() => setActiveSection("data")}
              type="button"
            >
              Your data
            </button>
          </div>
        </aside>

        <section className="profile-main">
          <div className="profile-heading">
            <p className="profile-kicker">{activeSection === "profile" ? "Account" : "Your data"}</p>
            <h2>{activeSection === "profile" ? "Personal settings" : "Data controls"}</h2>
            <p>
              {activeSection === "profile"
                ? "Review your account and manage exported or deleted data."
                : "Delete the memory data tied to this account without removing your login."}
            </p>
          </div>

          {statusMessage ? <div className="profile-status">{statusMessage}</div> : null}
          {error ? <div className="error-banner">{error}</div> : null}

          {activeSection === "profile" ? (
            <article className="profile-card">
              <div className="profile-card-header">
                <h3>Account</h3>
                <p>This is the only place the signed-in account and workspace details are shown.</p>
              </div>

              <div className="profile-card-grid">
                <div className="profile-field">
                  <span>Username</span>
                  <strong>{username}</strong>
                </div>
                <div className="profile-field">
                  <span>Email</span>
                  <strong>{email}</strong>
                </div>
                <div className="profile-field">
                  <span>Workspace</span>
                  <strong>{username}&apos;s Workspace</strong>
                </div>
              </div>

              <div className="profile-card-actions">
                <button className="profile-logout-button" onClick={handleLogout} type="button">
                  Log out
                </button>
              </div>
            </article>
          ) : (
            <article className="profile-card">
              <div className="profile-card-header">
                <h3>Your data</h3>
                <p>
                  This clears your journal history and its derived artifacts, but it does not delete
                  your account or sign you out.
                </p>
              </div>

              <div className="profile-card-grid profile-data-grid">
                <div className="profile-field">
                  <span>Postgres</span>
                  <strong>Journal entries, projection jobs, clarifications, and alias resolutions.</strong>
                </div>
                <div className="profile-field">
                  <span>Weaviate</span>
                  <strong>Vector memory artifacts generated from your journal history.</strong>
                </div>
                <div className="profile-field">
                  <span>Neo4j</span>
                  <strong>Knowledge graph observations, entities, and relationships for this account.</strong>
                </div>
              </div>

              <div className="profile-danger-zone">
                <div>
                  <p className="profile-danger-title">Delete all data</p>
                  <p className="profile-danger-copy">
                    This action removes account-linked memory data across all local stores and cannot
                    be undone.
                  </p>
                </div>
                <button
                  className="profile-delete-button"
                  disabled={isDeletingData || isWipingLocalData}
                  onClick={() => void handleDeleteData()}
                  type="button"
                >
                  {isDeletingData ? "Deleting..." : "Delete all data"}
                </button>
              </div>

              {isDevelopment ? (
                <div className="profile-danger-zone profile-danger-zone-dev">
                  <div>
                    <p className="profile-danger-title">Developer local wipe</p>
                    <p className="profile-danger-copy">
                      Deletes all local memory data for every account in this environment, including
                      Weaviate objects and schema plus the Neo4j graph. User accounts are preserved.
                    </p>
                  </div>
                  <button
                    className="profile-delete-button profile-delete-button-dev"
                    disabled={isDeletingData || isWipingLocalData}
                    onClick={() => void handleWipeLocalData()}
                    type="button"
                  >
                    {isWipingLocalData ? "Wiping..." : "Wipe local data"}
                  </button>
                </div>
              ) : null}
            </article>
          )}

          {activeSection === "data" && cleanup.length > 0 ? (
            <article className="profile-card">
              <div className="profile-card-header">
                <h3>Last cleanup</h3>
                <p>Latest delete run for this account.</p>
              </div>

              <div className="profile-cleanup-grid">
                {cleanup.map((item) => (
                  <div className="profile-field" key={item.store}>
                    <span>{item.store}</span>
                    <strong>{item.success ? `${item.deleted_count} records removed` : "Cleanup failed"}</strong>
                    {item.error ? <p className="profile-field-detail">{item.error}</p> : null}
                  </div>
                ))}
              </div>
            </article>
          ) : null}
        </section>
      </section>
    </main>
  );
}
