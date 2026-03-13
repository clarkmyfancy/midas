import Link from "next/link";

export default function HomePage() {
  return (
    <main className="page">
      <section className="hero hero-grid">
        <div>
          <p className="eyebrow">Midas Workspace</p>
          <h1>Local accounts. Real backend. Live model tokens in the browser.</h1>
          <p className="lede">
            Sign in on the web, persist users in Postgres, and watch the reflection
            stream arrive from the running FastAPI backend as the model emits tokens.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" href="/login">
              Create an account
            </Link>
            <Link className="button button-secondary" href="/chat">
              Open chat
            </Link>
          </div>
        </div>

        <div className="panel status-panel">
          <div className="status-stack">
            <div>
              <p className="eyebrow">Flow</p>
              <h2>From browser to model output</h2>
            </div>
            <ul className="timeline">
              <li>Register or log in against the FastAPI auth endpoints.</li>
              <li>Store the returned bearer token locally in the browser.</li>
              <li>Send a reflection message to the streaming backend route.</li>
              <li>Render each SSE token into the active assistant bubble live.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="card-grid">
        <article className="panel">
          <p className="eyebrow">Auth</p>
          <h2>Real user accounts</h2>
          <p>
            When Postgres is running, registrations persist in the local database
            instead of memory. Each account gets its own bearer token and thread key.
          </p>
        </article>

        <article className="panel">
          <p className="eyebrow">Streaming</p>
          <h2>Actual token scroll</h2>
          <p>
            The chat page consumes the backend SSE stream directly so you can watch
            tokens appear as the model produces them.
          </p>
        </article>

        <article className="panel">
          <p className="eyebrow">Local-first</p>
          <h2>Simple local stack</h2>
          <p>
            The web app talks to the backend over HTTP on localhost, and Postgres is
            available via the repository Docker Compose file when you want persistence.
          </p>
        </article>
      </section>
    </main>
  );
}
