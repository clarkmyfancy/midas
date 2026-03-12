import type { ReactNode } from "react";

type CapabilityMap = Record<string, boolean>;

type FeatureGateProps = {
  capability: string;
  capabilities: CapabilityMap;
  children: ReactNode;
  title?: string;
  description?: string;
};

export function FeatureGate({
  capability,
  capabilities,
  children,
  title = "Upgrade to Pro",
  description = "This capability is available in the Pro tier.",
}: FeatureGateProps) {
  if (capabilities[capability]) {
    return <>{children}</>;
  }

  return (
    <div className="feature-lock" data-feature={capability}>
      <span className="feature-badge">Pro Feature</span>
      <h3>{title}</h3>
      <p>{description}</p>
      <button type="button">Upgrade to Pro</button>
    </div>
  );
}

