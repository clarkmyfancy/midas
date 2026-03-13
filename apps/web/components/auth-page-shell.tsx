"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../lib/api";
import { useAuth } from "./auth-provider";

type AuthMode = "register" | "login";

export function AuthPageShell() {
  const router = useRouter();
  const { isReady, session, login, register } = useAuth();
  const [mode, setMode] = useState<AuthMode>("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (isReady && session) {
      router.replace("/chat");
    }
  }, [isReady, router, session]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsPending(true);
    setError(null);
    setSuccess(null);

    try {
      if (mode === "register") {
        await register({ email, password });
        setSuccess("Account created and signed in. Redirecting to chat.");
      } else {
        await login({ email, password });
        setSuccess("Signed in. Redirecting to chat.");
      }

      router.push("/chat");
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(caughtError.message);
      } else {
        setError("Unable to complete the request.");
      }
    } finally {
      setIsPending(false);
    }
  }

  return (
    <main className="page auth-layout">
      <section className="panel">
        <p className="eyebrow">Account</p>
        <h1>{mode === "register" ? "Create your local Midas account" : "Sign back in"}</h1>
        <p className="lede">
          This page calls the real backend auth endpoints and stores the returned bearer
          token in the browser for the chat session.
        </p>

        <div className="auth-toggle" role="tablist" aria-label="Authentication mode">
          <button
            className={mode === "register" ? "button button-primary" : "ghost-button"}
            onClick={() => setMode("register")}
            type="button"
          >
            Create account
          </button>
          <button
            className={mode === "login" ? "button button-primary" : "ghost-button"}
            onClick={() => setMode("login")}
            type="button"
          >
            Log in
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="label">
            Email
            <input
              autoComplete="email"
              className="input"
              name="email"
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              type="email"
              value={email}
            />
          </label>

          <label className="label">
            Password
            <input
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              className="input"
              minLength={8}
              name="password"
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
              type="password"
              value={password}
            />
          </label>

          {error ? <div className="error-banner">{error}</div> : null}
          {success ? <div className="success-banner">{success}</div> : null}

          <div className="chat-actions">
            <button className="button button-primary" disabled={isPending} type="submit">
              {isPending
                ? "Submitting..."
                : mode === "register"
                  ? "Create account"
                  : "Log in"}
            </button>
            <Link className="link-button" href="/chat">
              View chat
            </Link>
          </div>
        </form>
      </section>

      <aside className="panel auth-side">
        <p className="eyebrow">Notes</p>
        <h2>Local persistence path</h2>
        <ul className="bullet-list">
          <li>With Postgres running, new users are stored in the `auth_users` table.</li>
          <li>Without Postgres, auth falls back to in-memory storage for quick local dev.</li>
          <li>The chat page uses the stored bearer token to stream live model output.</li>
        </ul>
        <p className="helper">
          If you are already signed in, this page will move you to{" "}
          <Link href="/chat">the chat workspace</Link>.
        </p>
      </aside>
    </main>
  );
}
