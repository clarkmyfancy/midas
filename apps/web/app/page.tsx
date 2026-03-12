import type { CapabilityMapResponse, ReflectionResponse } from "@midas/types";

import { FeatureGate } from "../components/feature-gate";

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

const capabilityMap: CapabilityMapResponse = {
  capabilities: {
    pro_analytics: false,
    weekly_reflection: false,
    mental_model_graph: false,
  },
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

      <section className="panel gate-panel">
        <h2>Feature Gate Preview</h2>
        <FeatureGate
          capability="weekly_reflection"
          capabilities={capabilityMap.capabilities}
          description="Unlock the high-reasoning weekly coach and long-horizon synthesis."
        >
          <div className="feature-unlocked">
            <h3>Weekly Reflection</h3>
            <p>{preview.summary}</p>
          </div>
        </FeatureGate>
      </section>
    </main>
  );
}
