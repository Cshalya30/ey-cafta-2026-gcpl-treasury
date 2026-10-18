# 5. Security posture for a synthetic-data demonstration

**Status** Accepted · **Date** 18 October 2026

## Context

The application holds synthetic data and moves no money. It would be defensible
to skip most hardening. It would also teach the wrong lesson: the deployment
story is part of the recommendation being made to a Treasury Committee, and a
console that ships with a wildcard CORS policy undermines the argument that this
team understands controls.

## Decision

Implement the controls for real, and be honest about which are load-bearing here
and which exist because a real deployment needs them.

**Real controls, doing real work today**

- ABAC resolved server-side; 403 for out-of-scope, never a filtered 200
- Persona capability enforcement on every write
- Parameterised queries throughout (SQLAlchemy); no string-built SQL
- Pydantic validation with explicit bounds on every request field
- `X-Persona` pattern-validated, so an injection payload cannot reach a lookup
- Security headers on every response including errors; `Cache-Control: no-store`
  so figures never reach a shared cache
- Exact CORS origins, never a wildcard
- Rate limiting on writes
- No full account number may reach the database, enforced by test
- No secret in the repository; the session key defaults to random per boot

**Conditional, for a real deployment** — see ADR 0002

- Session cookie, CSRF double-submit, HSTS, HTTPS redirect, closed `/docs`

**Deliberately absent**

- Payment credentials, bank connectivity, PII of any kind. The application has
  none to protect, and adding a credential store to a demonstration would be the
  only genuinely dangerous thing in it.

## Consequences

- `GCPL_FORCE_HTTPS=1` must only be set behind a TLS terminator: a `Secure`
  cookie on plain localhost is silently dropped and the session fails.
- The storage-consent notice describes what the application actually does — two
  preferences in `localStorage` — rather than reciting a cookie banner it does
  not need. Declining genuinely prevents the write, via a guarded storage
  adapter, rather than only hiding the notice.
