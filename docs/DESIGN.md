# Design contract

The register is **operational**, not analytical: time-sensitive, continuously
changing, monitored at a glance. Everything below follows from that one
sentence. Where a choice would make this read as a generic SaaS dashboard, the
choice is wrong.

Tokens live in `web/src/styles/tokens.css`. Motion lives in `motion.css`. This
document says *why*; the CSS says *what*.

---

## 1. Density

| Surface | Row height | Source |
|---|---|---|
| Blotters, audit stream, coverage grid | **24 px** | Carbon `xs` — "information fit over comfort" |
| Primary tables | **32 px** | Carbon `sm` |
| Forms, settings | 40 px | Carbon `md` |

Header rows, toolbars, batch-action bars and pagination match the body row size.

Carbon `md` at 40 px is the generic SaaS default. Using it everywhere would make
an operations console read as a web app, and would cost roughly a third of the
rows visible on a 900 px viewport — which is the product.

---

## 2. Colour

Base surface **#161616** (Carbon Gray 100). Near-black, not pure black: pure
black makes every border either invisible or harsh.

Radix 12-step semantics:

| Steps | Role |
|---|---|
| 1–2 | App and card backgrounds |
| 3–5 | Component backgrounds: normal, hover, pressed |
| 6–8 | Borders: subtle, subtle-interactive, strong-interactive and focus |
| 9–10 | Solid fills; 9 is the highest-chroma pure colour, 10 its hover |
| 11–12 | Low-contrast and high-contrast text |

**Elevation uses surface lightness, not shadow.** Each layer up is one step
lighter than the layer below. Shadows are hard to see on a near-black base and
read as smudge rather than depth.

**Status mapping.** Step 9 for the dot, step 3 for the row tint, step 11 for the
label. Green settled or within limit · amber approaching or pending · red breach
or failed · blue informational · indigo the single action accent.

### Two traps this project hit

- **Amber at step 9 needs dark text, not white.** The warning state here is
  amber, so this is not hypothetical. `--warn-on` exists for it.
- **Draw each border once.** Overlapping alpha borders produce visible
  intersections, and that is the commonest visual defect in a dense grid. Tables
  draw `border-bottom` only; panels use a single `inset` ring.

### Colour never carries quantity alone

Every lens pairs a hue with a glyph or a numeric badge, and every node card also
renders a magnitude bar. People do not perceive colour values as ordered, and a
reader who cannot distinguish the hue must still be able to rank the nodes.

---

## 3. Contrast floors

| Element | Minimum |
|---|---|
| Text under 24 px | 4.5:1 |
| Text 24 px and above | 3:1 |
| Graphical elements, chart lines, status dots | **3:1** |
| Focus indicators | **3:1** |

The last two are what dashboards systematically fail: a 2 px chart line or a
status dot at 2.1:1 on #161616 is non-compliant even when its label passes.

Axe runs against all five registers in CI and zero critical or serious
violations is a hard gate.

---

## 4. Typography

- Sans: **Inter**. Mono: **IBM Plex Mono**. Both ship `tnum`; verify before
  substituting anything.
- Numeric columns: `font-variant-numeric: tabular-nums lining-nums`. A test
  asserts this on the rendered table, because a column of proportional digits in
  a treasury grid is unreadable at a glance.
- Identifiers and account numbers add `slashed-zero`.
- `…` not `...`; curly quotes; non-breaking spaces in `⌘ K`; `text-wrap: balance`
  on headings.
- Brand names, currency codes and counterparty names carry `translate="no"`.

---

## 5. Tables

Designed against the four NN/g data-table tasks.

1. **Finding** — readable first-column identifier, columns ordered by
   importance, filters with a visible active state and a count.
2. **Comparing** — the header row and the identifier column both freeze; zebra
   striping plus hover highlighting; sort state lives in the URL.
3. **Viewing one row** — a **non-modal side panel**. Never a modal: a modal
   hides the adjacent records a treasury user is comparing against, which is the
   task they are in the middle of.
4. **Acting** — checkbox batch actions with Select All. While batch mode is
   active, single-row actions and row overflow menus are disabled.

Sort arrows appear on hover; only the sorted column keeps its icon. Any list
over 50 rows virtualizes.

---

## 6. The four states that are the normal case

Loading, empty, error and stale are not exceptions in treasury. Each is designed
rather than defaulted (`components/states.tsx`).

| State | Treatment |
|---|---|
| **Loading** | Skeleton rows matching the final row height exactly, so nothing shifts on resolve. Never a centred spinner over a table |
| **Empty, nothing yet** | States what is missing, who owns it, and the action. Never "No data" alone |
| **Empty, filtered out** | Distinct from the above. Names the filters applied and offers to clear them |
| **Stale** | The figure still renders, with an age badge. **Never hide a stale number** — hiding it makes the group look more current than it is |
| **Offline** | Last known value, its timestamp, and the gap. Marked excluded from aggregates, and that exclusion is stated on the aggregate |
| **Error** | Inline, in place, with a retry. Never a toast that disappears |
| **Forbidden** | "This entity is outside your scope", naming the persona's real scope. Never implies the data does not exist |
| **Partial** | Every aggregate carries a coverage figure. An aggregate without one is a lie by omission |

---

## 7. Motion

The motion personality is **restrained precision**. Motion exists to show
causation and state change; anything that draws the eye without telling the
reader something is a defect.

| Moment | Duration | Easing |
|---|---|---|
| Button press, hover | 120 ms | ease-out |
| Tooltip, dropdown, badge | 180 ms | ease-out |
| Card or panel entering | 240 ms | ease-out |
| Anything leaving | 180 ms (~75% of enter) | ease-in |
| Travelling across the viewport | 320 ms | ease-in-out |
| Gap between revealed list items | 40 ms stagger | — |

Three rules, all testable and all tested:

1. **Animate `transform` and `opacity` only.** Those composite off the main
   thread; width, height, top and box-shadow do not, and a dropped frame on an
   81-row grid is immediately visible.
2. **Leaving is faster than entering.** The reader has already decided to
   dismiss; making them wait feels broken.
3. **Every duration has a reduced-motion answer, and it is 1 ms** — not "animate
   anyway, slightly slower".

**The leak edge is the only looping animation in the product**, and it is
load-bearing: a dashed line travelling from a surplus entity to a borrowing one
is money leaving the group. Everything else on the Canvas holds still, which is
why it reads instantly. Under reduced motion it stops, and the dashes remain as
a still-distinguishable stroke.

`LiveValue` marks a figure that has just changed under the reader — a slider
drag, a rate edit. It is the one place a small overshoot is warranted, because
causation is the product's subject. It does nothing on first paint.

---

## 8. Platform hygiene

```css
html { color-scheme: dark; }
```
```html
<meta name="theme-color" content="#161616">
```

A native `<select>` needs explicit `background-color` **and** `color`, or it
renders unreadable in Windows dark mode.

### The cascade rule, learned the hard way

Tailwind v4 puts utilities in a cascade layer. **Unlayered CSS beats layered CSS
regardless of specificity.** An unlayered `a { color: var(--info-11) }` therefore
overrode a `text-white` utility and rendered the Canvas call-to-action at
3.28:1 until an Axe run caught it.

Base element styles live in `@layer base`, custom classes in `@layer components`,
and vendor stylesheets are imported with `layer(base)`.

---

## 9. Interaction

- Hover, active and focus must be **more** prominent than rest, not merely
  different.
- `:focus-visible` always; never `outline: none` without a replacement.
- Flex children need `min-w-0` or truncation silently fails.
- Destructive actions need a confirmation or an undo window. Non-negotiable for
  proposal authorisation, which is why a justification is required and recorded.
- Every stateful view is deep-linkable. This is a workflow requirement, not a
  nicety: treasury users paste views to approvers.
