# ADR 005: Infrastructure-as-Code via Pulumi

- Status: Accepted

## Context

Midas needs to manage cloud resources such as object storage, GPU endpoints, and databases in a way that is integrated with application logic and senior-level engineering workflows.

## Decision

Use Pulumi over Terraform.

## Consequences

### Positive

- Infrastructure can be written in Python or TypeScript, which fits the existing backend and web toolchain.
- General-purpose languages make it easier to integrate infrastructure logic with AI conductor tooling and shared type systems.

### Negative

- Pulumi has a smaller ecosystem of community modules and examples than Terraform.

## Alternatives Considered

- Terraform: Mature ecosystem, but its DSL is harder to integrate with general programming logic.
- AWS CDK: Strong developer experience on AWS, but too narrow for a cloud-agnostic architecture.

