# ADR 018: JWT Access and Refresh Session Architecture

- Status: Accepted

## Context

Midas needs authentication that:

- survives full page reloads in the web app
- works across Safari, Chrome, Firefox, and mobile browsers
- works for native mobile clients on iPhone now and Android later
- avoids coupling session continuity to browser cookie behavior

The previous web approach stored bearer access tokens directly in `localStorage`. That preserved sessions across reloads, but it made the long-lived credential trivially readable by any successful XSS payload.

## Decision

Adopt a two-token session model across clients:

- short-lived JWT access tokens are used for API authorization
- long-lived refresh tokens are used only to mint new access tokens
- refresh tokens rotate on every successful refresh
- logout revokes the active refresh token

Client storage is platform-specific:

- web keeps the access token only in memory and persists the refresh token in browser storage
- iOS keeps the refresh token in Keychain and restores a fresh access token on app launch
- Android should follow the same pattern using the platform secure store

The backend persists refresh sessions and validates rotation server-side.

## Consequences

### Positive

- Web users stay signed in across refreshes without depending on cookies.
- Native mobile clients get a stable session restoration path.
- Access tokens can be shorter lived than refresh tokens.
- Refresh token rotation limits the impact of token replay after logout or token replacement.

### Negative

- On the web, a stored refresh token is still readable by JavaScript and therefore remains exposed to XSS exfiltration.
- The backend auth model becomes more complex because it now needs refresh session persistence, rotation, and revocation.
- Clients must implement boot-time refresh and refresh-token replacement correctly.

## Implementation Notes

- Access tokens should remain the only credential sent in the `Authorization` header.
- Refresh tokens should never be embedded into URLs.
- Web code should persist only the refresh token, not the access token.
- Mobile clients should treat refresh tokens as secure-storage data, not plain preferences.
- Strong CSP and general XSS hardening remain mandatory because browser-readable refresh tokens expand the blast radius of any XSS bug.
