# Midas: High-Level Problem Specification

See also [docs/adr/001-repository-structure.md](docs/adr/001-repository-structure.md) for the accepted repository strategy behind the implementation.

## Overview

**App name:** Midas

Midas is a private, local-first, multi-agent personal growth system designed to detect and reduce **semantic drift**: the gap between who a person intends to become and the person their actual behavior, health data, and calendar patterns suggest they are becoming.

This project is both a personal operating system for self-reflection and a portfolio-grade example of secure, AI-augmented systems design.

## 1. The Story: Why This Matters

As a senior engineer in a high-velocity tech environment, life is often measured in sprints, pull requests, deadlines, and roadmap milestones. Professional progress is rigorously tracked, but personal growth usually is not.

Most people are drowning in personal data but starving for wisdom:

- Thousands of journal entries are captured and never meaningfully revisited.
- Health data shows symptoms such as poor sleep or low HRV without explaining likely causes.
- Calendars reveal where time went, but not whether that time aligned with values, goals, or identity.

Midas exists to close that gap. It is not just another tracker. It is a private coaching system that synthesizes subjective intent with objective evidence, helping a user audit the direction of their life with the same seriousness they apply to engineering systems.

## 2. Problem Statement

Personal growth tools currently fail in two major ways:

### Passive trackers

Tools like HealthKit and Oura provide raw metrics such as HRV, sleep, and activity, but they do not explain the behavioral or emotional context behind those changes.

### Active trackers

Tools like journaling apps capture subjective reflection, but those reflections are rarely audited across long time horizons for recurring patterns, inconsistencies, blind spots, or self-deception.

### Core opportunity

Midas bridges these two worlds through a zero-trust, local-first architecture that connects:

- **Subjective intent:** journals, reflections, goals, stated priorities
- **Objective reality:** biometrics, calendar activity, behavioral patterns

The result is a system that can identify whether a user's actions are moving them toward or away from the person they say they want to become.

## 3. Usage and Data Architecture

Midas operates as a hybrid ecosystem across iPhone and the web.

### Mobile experience (iPhone)

- **Active capture:** Native SwiftUI interface for multi-turn conversational journaling
- **Siri integration:** App Intents support for hands-free reflection sessions such as "Siri, start a Mirror reflection"
- **Biometric sync:** Automatic ingestion of steps, sleep stages, and heart rate variability from HealthKit
- **Privacy proxy:** On-device PII masking using regex and lightweight NER before text is sent to any high-reasoning backend

### Web experience (dashboard)

- **Semantic drift analysis:** React dashboard visualizing alignment between stated goals and actual activity
- **Deep weekly reflections:** Long-form summaries generated from the previous 7 days of vector memory
- **Knowledge graph:** Visual map of mental models, recurring blockers, and behavioral loops identified by agents

## 4. Technical Stack: Staff-Level Blueprint

| Component | Technology | Rationale |
| --- | --- | --- |
| Mobile | SwiftUI + HealthKit + App Intents | Native access to Apple security boundaries, biometrics, and voice workflows |
| Orchestration | LangGraph + FastAPI | Stateful multi-turn workflows and structured agent handoffs |
| Memory | Weaviate or Milvus | Vector retrieval with support for operationally safe migrations |
| Agents | Multi-agent architecture (Habit Analyst, Reflection Coach) | Specialized agents reduce context noise and improve accuracy |
| Security | E2B sandboxes + Microsoft Presidio | Isolate risky workloads and redact PII at the edge |
| Infrastructure | Pulumi or Terraform | Professional-grade infrastructure as code |
| MLOps | LangSmith + Arize Phoenix | Evaluation, tracing, and local-first RAG observability |

## 5. Staff-Level Skills Development: AI-Augmented Conductor

This project is not only a product. It is also a deliberate vehicle for leveling up from implementation-focused engineering to systems leadership.

Key skills developed through Midas:

- **Architecture Decision Records (ADRs):** Documenting why key decisions were made, such as local vs. cloud tradeoffs
- **Prompt engineering as system design:** Designing agentic workflows with scoped tools and least-privilege permissions
- **Deployment gap mastery:** Building durable state persistence and audit trails so agents remain reliable across restarts
- **Automated probabilistic testing:** Using LLM-as-a-judge and trajectory evaluation to measure whether the system identifies real drift instead of hallucinating insight

## 6. GitHub Monetization Strategy

Midas should be structured to support open-source credibility and commercial upside at the same time.

### Open core

Keep the local-first iOS core and baseline orchestration open source under a permissive license such as MIT or Apache 2.0. Reserve advanced features such as cloud sync, multi-user insights, and proactive notification agents for paid tiers.

### Dual licensing

Offer the repository under a copyleft license for open usage while selling commercial licenses to companies that want to embed the reflection engine in proprietary wellness or coaching products.

### Managed SaaS

Offer a hosted Midas Cloud for users who do not want to self-host infrastructure such as FastAPI services, vector databases, or GPU-backed model endpoints.

### App Store revenue

Monetize the iOS experience through subscriptions, potentially using RevenueCat, while keeping the backend and core orchestration visible as proof of technical depth.

## 7. Implementation Roadmap: Synthetic to Real

### Phase 1: Synthetic testing

Generate 90 days of synthetic journal and HealthKit-style data using an LLM-based population generator. This provides a safe dataset for initial agent testing without exposing personal data.

### Phase 2: Security sandbox

Deploy agent workflows inside E2B microVMs so that analysis of imported files such as calendar exports happens in isolated execution environments.

### Phase 3: Personal pivot

Replace synthetic data with real HealthKit and personal reflection data. Use ADRs to document the transition from development and testing into a trusted production-grade personal system.

## 8. Expected Outcome

By the end of the project, Midas should function as both:

- A private AI coaching system for personal growth
- A public portfolio artifact demonstrating secure, scalable, commercially aware AI systems design

The repository should ultimately showcase the ability to design and ship systems that combine privacy, memory, multi-agent orchestration, and practical product strategy into a coherent whole.
