"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "./auth-provider";

function deriveUsername(email: string) {
  return email.split("@")[0] || email;
}

export function ProfilePageShell() {
  const router = useRouter();
  const { isReady, logout, session } = useAuth();

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
            <div className="profile-sidebar-link profile-sidebar-link-active">Profile</div>
            <div className="profile-sidebar-link">Your data</div>
          </div>
        </aside>

        <section className="profile-main">
          <div className="profile-heading">
            <p className="profile-kicker">Account</p>
            <h2>Personal settings</h2>
            <p>Review your account and manage exported or deleted data.</p>
          </div>

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
                <strong>{username}'s Workspace</strong>
              </div>
            </div>

            <div className="profile-card-actions">
              <button className="profile-logout-button" onClick={handleLogout} type="button">
                Log out
              </button>
            </div>
          </article>
        </section>
      </section>
    </main>
  );
}
