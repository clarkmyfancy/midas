---
name: secure-sandboxing
description: Build PII-safe sandbox execution paths for Midas. Use when code needs to send user files, journal data, or derived analytics into an isolated runtime such as E2B, especially for CSV analysis or other untrusted code execution. Keep raw data local, scrub or anonymize it before sandbox ingress, and follow the E2B plus Presidio template in `references/e2b-presidio-template.md`.
---

# Secure Sandboxing

## Required Workflow

1. Keep the raw source data in the trusted host process. Do not upload raw user files to a sandbox by default.
2. Classify the data before execution. If the payload can contain names, emails, phone numbers, dates of birth, addresses, identifiers, or free-form journal text, treat it as sensitive.
3. Run local PII detection and anonymization before sandbox ingress. Prefer Presidio. Use regex fallbacks only when Presidio is unavailable.
4. Send only the minimum sanitized payload plus the task-specific code into the sandbox.
5. Keep the token-to-original mapping outside the sandbox if the task requires later rehydration.
6. Destroy the sandbox after use and avoid persistent snapshots unless the user explicitly needs them.

## Engineering Rules

- Prefer local execution when a task does not require dynamic third-party code.
- Never pass API keys, auth cookies, or long-lived tokens into the sandbox image.
- Mount or upload only the specific file subset needed for the task.
- Log whether data was raw, scrubbed, or synthetic.
- Fail closed if the scrubber cannot classify the input with confidence.

## Midas-Specific Notes

- HealthKit-derived payloads, journal entries, and calendar text should be assumed sensitive.
- If a workflow claims to need raw PII inside the sandbox, require an explicit justification in the code review.
- Preserve the distinction between Core-safe local processing and Pro or hosted analytics.

## Resource

- Load `references/e2b-presidio-template.md` for the sandbox setup template and the local regex fallback patterns.
