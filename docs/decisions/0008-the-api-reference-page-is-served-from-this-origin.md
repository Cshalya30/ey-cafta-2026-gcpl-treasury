# 8. The API reference page is served from this origin

**Status** Accepted · **Date** 19 October 2026 · **Extends** [0007](0007-one-origin-and-two-content-security-policies.md)

## Context

PRD section 13 requires the application to run with no network beyond
localhost, with every font and asset self-hosted. The application honoured
that. FastAPI's `/docs` page never did.

The HTML FastAPI generates for Swagger UI hardcodes four external references:
`swagger-ui.css` and `swagger-ui-bundle.js` on `cdn.jsdelivr.net`, a favicon on
`fastapi.tiangolo.com`, and an inline `<script>` that calls `SwaggerUIBundle`.
Under this application's policy the browser blocked all four, and the page
rendered blank with four console violations.

This was not introduced by the deployment. It has been true since
`feat(security)` set `Content-Security-Policy` on every response, which means
`/docs` had been broken on localhost for as long as the header existed — and
the README advertised the page throughout. Nothing failed server-side, no test
covered it, and the only evidence was a blank page nobody opened.

It surfaced on the deployment because a public URL made `/docs` reachable by a
judge rather than only by the people who already knew what the API looked like.

## Decision

Serve the reference page ourselves, from vendored assets.

`swagger-ui.css` and `swagger-ui-bundle.js` are committed under
`api/swagger_assets/` at a pinned version. `api/docs.py` builds the page and
mounts those assets at `/docs-assets`. FastAPI's own page is disabled with
`docs_url=None`; the gate stays the same property as before, so the page is
still closed when `GCPL_ENV=prod`.

**The bootstrap is a file, not an inline script.** `docs-init.js` holds the
`SwaggerUIBundle` call. This is the whole reason a third policy can afford to
be strict: an inline script would need `'unsafe-inline'`, a hash or a nonce on
`script-src`, and the first of those is a real weakening on a page that renders
an OpenAPI document. Keeping the call in a file leaves `script-src 'self'` with
no escape at all, the same rule the application runs under.

So there are three policies, selected by request path:

| | `/api/*`, `/health`, `/openapi.json` | `/docs`, `/docs-assets/*` | the app |
|---|---|---|---|
| `default-src` | `'none'` | `'none'` | `'self'` |
| `script-src` | — | `'self'` | `'self'` |
| `style-src` | — | `'self' 'unsafe-inline'` | `'self' 'unsafe-inline'` |

`'unsafe-inline'` appears for styles only, in both document policies, because
Swagger UI and React alike set style attributes that cannot be hashed.

The page also carries a persona selector, which sets `X-Persona` through
Swagger's `requestInterceptor`. Without it every "Try it out" answers 422,
since every endpoint but the session pair requires the header — a reference
page where no example works is worse than none. With it, the scope model is
explorable from the documentation: `GET /api/v1/entities/GCPL-GB` returns 200
as P2 and 403 as P5, which is the product's argument, demonstrated rather than
asserted.

### The one that localhost could not have caught

Swagger's `validatorUrl` defaults to `https://validator.swagger.io/validator`,
and the bundle renders a badge that calls it with this API's spec URL attached.
The badge is suppressed when the spec URL contains `localhost` or `127.0.0.1`.

So the default would have reintroduced a third-party call on the deployment and
nowhere else — invisible to every local check, visible only on the public URL a
judge opens. It is disabled with `validatorUrl: null`.

This is the second time in this change that the real failure was one no local
run could see. It is worth stating the lesson rather than only the fix: for a
rule about what the application reaches over the network, "it works on my
machine" is not weak evidence, it is evidence of the wrong thing.

## Consequences

About 1.6MB of vendored third-party build is now committed. That is the price
of the offline requirement, and it is paid once.

`api/swagger_assets/` joins `node_modules` and `dist` in the number guard's
skip list. Minified upstream CSS is full of hex colours and percentages that
nobody here chose, and the guard exists to police the figures this team writes.

Seven tests cover the page. The two that matter assert that no third-party
host appears in its markup and that the validator is off, which are the two
ways the offline rule was actually broken. The original failure was silent;
these would not be.

Upstream's `LICENSE` is vendored beside the assets, because Apache-2.0 and MIT
both require the notice to travel with a redistributed copy. The three files
are marked `linguist-vendored`, so GitHub's language statistics describe the
work in this repository rather than 1.4MB of minified Swagger UI.

The vendored assets must be refreshed deliberately. Pinning them means a
Swagger upgrade is a commit rather than a surprise on someone else's CDN, which
is the trade the offline rule was asking for in the first place.
