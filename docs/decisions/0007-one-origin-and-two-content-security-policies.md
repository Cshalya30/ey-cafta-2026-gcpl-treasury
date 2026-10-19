# 7. The app is served from the API, under two content security policies

**Status** Accepted · **Date** 19 October 2026

## Context

The demo had to be reachable on a public URL for roughly a month of judging,
from a repository with no Docker and no deploy CLI on the authoring machine.

The shape of the deployment was not actually a free choice. Two existing
decisions had already made it:

- `web/src/lib/api.ts` sets `BASE = '/api/v1'`, a relative path. The client has
  no configurable origin.
- Decision 0005 made the CSRF guard a double-submit cookie pair, and the
  session cookie `SameSite=Strict`.

Splitting the page onto a static host and the API onto another would mean a
cross-origin credentialled fetch, `SameSite=None` on the session cookie, and a
CORS allowance for a browser origin — a materially weaker posture than the one
decision 0005 argued for, in exchange for nothing. PRD section 6.1 had already
anticipated the answer by listing a static mount in `main.py`.

The obstacle was that `SecurityHeadersMiddleware` applied one policy to every
response, and that policy is `default-src 'none'`. It is correct for the API,
which serves JSON and embeds nothing. Applied to the document it blocks the
app's own stylesheet and bundle, and the page renders blank with no error the
server can see.

## Decision

One image, one origin, one process. FastAPI serves the built app at the root
and the API under `/api/v1`, and the policy is chosen per request path:

| | `/api/*` and `/health` | everything else |
|---|---|---|
| CSP | `default-src 'none'` | `default-src 'self'` |
| Cache-Control | `no-store` | `no-store`, except hashed assets |

`APP_CSP` carries `'unsafe-inline'` for `style-src` and for nothing else. The
app has an inline `<style>` block in `index.html` that paints the background
before the bundle parses, and 56 `style={{…}}` props that React applies as
inline style attributes; a style attribute is blocked by `style-src` without
it, and attributes cannot be hashed. `script-src` stays `'self'`, with no
`'unsafe-eval'` and no CDN, which is where the real XSS risk would be.

Content-hashed files under `/assets/` are cached for a year. Nothing there
carries a financial figure: every number reaches the page from the API, which
stays `no-store`. The shell is excluded so a redeploy is picked up on the next
load. A 404 under `/assets/` is excluded too — otherwise one bad deploy is
pinned in every visitor's browser until expiry.

Two smaller consequences fell out of testing it:

- A miss under `/assets/` returns 404 rather than the shell. Serving HTML under
  a `.js` URL would be rejected on `nosniff` anyway, and more confusingly.
- `/health` is exempt from the HTTPS redirect. A platform probe reaches the
  container on plain HTTP behind the proxy that terminates TLS and carries no
  `x-forwarded-proto`; redirecting it marks the service unhealthy and restarts
  it in a loop. The probe discloses a status string.

The deployment runs `GCPL_ENV=dev`. Decision 0002 established that the persona
switcher *is* the demonstration — a judge must be able to become a Front Office
Dealer and watch the API refuse an approval — and there is no sign-in screen in
`web/src` for a session gate to use. `GCPL_ENV=prod` on a public URL would
therefore mean a console nobody can write to and no way to authenticate from
the browser. Capability enforcement and ABAC run in both modes regardless, so
what is relinquished is the session gate alone, over synthetic data, in an
application that moves no money.

## Consequences

The filesystem is ephemeral, so a restart returns the demo to the seed-42
dataset. For a link that strangers can write to, that is the behaviour we want:
accumulated clutter clears itself.

The database is seeded at image build time rather than at boot. The generator
asserts INV-1 through INV-3 and exits non-zero, so a broken invariant now fails
the build instead of surfacing in front of a judge.

`web/dist` is absent in development and under pytest, so `mount_spa` returns
False and the API behaves exactly as it did before. The Vite dev server keeps
proxying `/api` to port 8000. The tests that cover the mount skip themselves
when the build is absent rather than failing.

The free tier spins down when idle and the next request pays a cold start. That
is the one weakness of this setup and it is a scheduling risk, not a technical
one: an external uptime check against `/health` keeps the service warm, and the
paid tier removes the behaviour outright.
