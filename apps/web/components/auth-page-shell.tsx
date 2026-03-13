"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../lib/api";
import { useAuth } from "./auth-provider";

type AuthMode = "register" | "login";

export function AuthPageShell() {
  const router = useRouter();
  const { isReady, session, login, register } = useAuth();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (isReady && session) {
      router.replace("/");
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
        setSuccess("Account created and signed in. Redirecting to reflect.");
      } else {
        await login({ email, password });
        setSuccess("Signed in. Redirecting to reflect.");
      }

      router.push("/");
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
    <main className="page auth-page-simple">
      <section className="auth-card">
        <p className="auth-brand">MIDAS</p>
        <h1 className="auth-title">{mode === "register" ? "Create account" : "Sign in"}</h1>
        <p className="auth-copy">
          You need an account to access the workspace and your private data.
        </p>

        <form className="auth-form auth-form-card" onSubmit={handleSubmit}>
          <label className="auth-field-label">
            Email
            <input
              autoComplete="email"
              className="auth-input"
              name="email"
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              type="email"
              value={email}
            />
          </label>

          <label className="auth-field-label">
            Password
            <input
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              className="auth-input"
              minLength={8}
              name="password"
              onChange={(event) => setPassword(event.target.value)}
              placeholder=""
              type="password"
              value={password}
            />
          </label>

          {error ? <div className="error-banner">{error}</div> : null}
          {success ? <div className="success-banner">{success}</div> : null}

          <div className="auth-actions">
            <button className="auth-submit-button" disabled={isPending} type="submit">
              {isPending
                ? "Submitting..."
                : mode === "register"
                  ? "Create account"
                  : "Sign in"}
            </button>
          </div>
        </form>

        <p className="auth-switch-copy">
          {mode === "register" ? "Already have an account? " : "Need an account? "}
          <button
            className="auth-switch-link"
            onClick={() => setMode(mode === "register" ? "login" : "register")}
            type="button"
          >
            {mode === "register" ? "Sign in" : "Create one"}
          </button>
        </p>
      </section>
    </main>
  );
}
