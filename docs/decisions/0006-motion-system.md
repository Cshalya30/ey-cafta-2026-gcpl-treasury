# 6. Motion is a token system, and most animation tooling was rejected

**Status** Accepted · **Date** 18 October 2026

## Context

An operations console watched at a glance has a very small motion budget. Ad hoc
durations scattered across components drift, and nothing enforces the
reduced-motion path.

Seven public animation and design skill sets were evaluated for this product:
Three.js, GSAP, Design DNA, Motion Design, Genjutsu, Animate and HyperFrames.

## Decision

Adopt **principles**, not libraries.

**Installed** into `.claude/skills/`, both library-agnostic and both arguing for
restraint, transform/opacity only, and an explicit reduced-motion path:

- `motion-design` (LottieFiles) — timing and easing tables, choreography,
  "decide the motion before the code"
- `animate`, `review-animations`, `animation-performance`,
  `find-animation-opportunities` (Emil Kowalski) — a review gate for motion

**Rejected, with reasons**

| Tool | Why not |
|---|---|
| Three.js | 3D scenes, GLTF, post-processing. A treasury console with a 3D hero reads as a product marketing page, and it would cost the Lighthouse 90+ and sub-1.5 s FCP targets |
| GSAP | Excellent, and the wrong trade here. ScrollTrigger is a scroll-story pattern for a page that scrolls; this app sets `overflow: hidden` on `body`. Adding an animation runtime to a product whose whole budget is a 120 ms press and a 240 ms panel entrance is weight for nothing |
| Design DNA | Derives tokens from screenshots of a reference design. This product already has a design contract — Carbon density, Radix 12-step, stated contrast floors — and deriving a second one would conflict with it and risk copying another firm's brand |
| Genjutsu | Creative coding for landing pages and whole-site builds. Wrong register, and the expensive mode builds a site this project already has |
| HyperFrames | Renders MP4 from HTML. Not a UI tool at all. Genuinely useful for the separate four-minute video deliverable; nothing to do with the application |

## Implementation

Durations and easings live in `web/src/styles/motion.css` as tokens. Components
reference `--t-enter`, `--e-out` and so on; they never write a number.

The rules are enforced by Playwright rather than by review:

- `nothing animates a layout property` walks the rendered DOM for any transition
  on a non-composited property, and for `transition: all`
- `reduced motion collapses every transition and stops the loop` loads the page
  under `prefers-reduced-motion: reduce` and asserts every token is 1 ms and the
  leak edge's `animation-name` is `none`

## Consequences

- Changing the product's motion personality is a change to one file.
- A contributor who writes `transition: all` fails CI rather than review.
- The leak edge is the single exception to "nothing loops", and it is documented
  as load-bearing in `docs/DESIGN.md`: a dashed line travelling from a surplus
  entity to a borrowing one is money leaving the group.
