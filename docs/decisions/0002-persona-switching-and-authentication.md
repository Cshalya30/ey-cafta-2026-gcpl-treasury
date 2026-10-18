# 2. Authentication is conditional on environment

**Status** Accepted · **Date** 18 October 2026

## Context

The PRD designs persona switching as a free demonstration mechanic: a judge
becomes a Front Office Dealer and watches the API refuse an approval. That
interaction *is* the product's argument.

A separate hardening requirement asks for authentication, protected admin
routes, CSRF protection and secure cookies.

These pull in opposite directions. Putting a login in front of a two-command
localhost demo breaks the demo for no security gain: the data is synthetic, the
application holds no credentials and it initiates no payments.

## Decision

Gate on environment rather than choosing one or the other.

- `GCPL_ENV=dev` (default): writes are open, persona switching is free.
- `GCPL_ENV=prod`: a signed `HttpOnly`, `SameSite=Strict` session cookie is
  required for every write, a double-submit CSRF token must match, and
  `GCPL_ACCESS_KEY` must be configured or `/session` refuses to issue anything
  at all — fail closed, not open.

**Capability enforcement is never conditional.** Who may approve, who may settle
and who may see amounts is enforced identically in both environments, because
that is the product's actual subject rather than a deployment concern.

Rate limiting applies to writes in both environments.

## Consequences

- The demo stays two commands.
- A real deployment is one environment variable away from being properly gated.
- The split must be explained rather than discovered: `GET /session` reports
  which mode it is in and says so in prose.
