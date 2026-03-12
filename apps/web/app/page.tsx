import type { ReflectionResponse } from "@midas/types";

const preview: ReflectionResponse = {
  summary:
    "Midas highlights semantic drift between stated priorities and observed activity patterns.",
  findings: [
    "Energy appears constrained after late-night work blocks.",
    "Movement is present but inconsistent across the week.",
  ],
  trace: [
    "habit_analyst: reviewed synthetic journal patterns",
    "reflection_coach: generated weekly coaching summary",
  ],
};

export default function HomePage() {
  return (
    <main className="page">
      <section className="hero">
        <p className="eyebrow">Midas</p>
        <h1>Private reflection infrastructure across iPhone, web, and API.</h1>
        <p className="lede">
          The monorepo keeps contracts shared across the backend, dashboard, and
          future mobile integrations.
        </p>
      </section>

      <section className="panel">
        <h2>Shared Contract Preview</h2>
        <p>
          This card is typed from the backend-generated Pydantic contract stored in
          <code>@midas/types</code>.
        </p>
        <pre>{JSON.stringify(preview, null, 2)}</pre>
      </section>
    </main>
  );
}

