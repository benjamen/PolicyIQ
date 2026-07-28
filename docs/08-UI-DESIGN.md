# UI Design System

Interactive mockup (Dashboard / Search / Compare / Admin, light + dark): see the artifact
delivered with this PR. It's a static HTML mock, not shippable code — the Vue 3 implementation
in Phase 1 weeks 11–12 should treat it as the source of truth for tokens and page composition,
not be built by re-guessing from this description.

## Why this direction

The brief listed page names and "dark mode" with no design point of view. The product's actual
differentiator is trust — every answer is only as good as its citation — so the UI treatment
is built around **evidence as a first-class visual element**, not a footnote: citation chips
(document · page · paragraph · verification checkmark) appear inline wherever the system makes
a claim, styled with the same weight as the claim itself.

## Tokens

**Color** — a cool, considered neutral (not the default warm-cream/near-black split), with one
accent tied to the product's meaning (verification/trust) and two semantic colors kept
deliberately separate from it (change/attention, exclusion/critical) so status reads at a
glance without competing with the brand accent:

| Token | Light | Dark | Use |
|---|---|---|---|
| `ink` / `text` | `#12181D` | `#EEF0EC` | Primary text |
| `paper` | `#F1F2ED` | `#0D1215` | App background |
| `paper-raised` | `#FFFFFF` | `#161D21` | Cards, table headers |
| `teal` (accent) | `#0B6E5A` | `#33A98A` | Primary actions, verified state, active nav |
| `slate` | `#5C6670` | `#8B95A0` | Secondary text, borders, neutral pills |
| `amber` (semantic) | `#A8650F` | `#D99A3D` | Change/attention (benefit increases, review queue) |
| `brick` (semantic) | `#A83E32` | `#D17A6D` | Critical (exclusions, crawl failures) |

Both themes are tuned independently (not a naive invert) — dark-mode teal is brightened for
contrast against the near-black ground, semantic colors likewise re-balanced.

**Type** — three roles, not one default sans everywhere:
- **Serif display** (`ui-serif, "Iowan Old Style", Georgia, serif`) for headings and the AI
  answer text itself — gives the extracted/generated content a "this came from a document"
  gravitas distinct from UI chrome.
- **System sans** for all interface chrome (nav, labels, buttons, tables).
- **Tabular monospace** (`ui-monospace`, `font-variant-numeric: tabular-nums`) for every number
  that needs to be scanned or compared: confidence scores, page/paragraph refs, dollar limits,
  stat tiles. This is deliberate — a data-comparison product should make its numbers easy to
  eyeball down a column.

**Layout** — compact icon+label nav rail (app-shell pattern, not a marketing top-nav), content
organized as cards/tables with `gap`-based spacing, wide tables (the comparison view) scroll in
their own container so the page itself never scrolls horizontally.

## Component notes for implementation

- **Citation chip** is the one component every other page reuses (Search answers, Compare cell
  refs, Document Explorer, Recent Changes feed). Build it once in `frontend/src/components/`
  before building the pages that consume it.
- **Confidence bar + score** always render together (bar for at-a-glance scanning, exact number
  for precision) — matches the "every fact carries a confidence score" requirement from the
  extraction strategy, made visible rather than buried in a tooltip.
- Status pills (`ok`/`warn`/`bad`/`neutral`) map directly to the admin endpoints in
  `03-API-SPEC.md` (crawler status, extraction confidence, embedding coverage) — same visual
  language for pipeline health as for user-facing content confidence, since they're the same
  underlying trust signal.
- **States** (loading / error / auth-redirect / empty, see `11-DATA-CONNECTION.md`) are a
  reusable pattern, not a one-off per view: skeleton cards for loading, a `brick`-toned retry
  card for errors (fail-closed, never a silent blank state), redirect-to-login on `401`, and an
  explicit "not found in indexed documents" rendering for empty/insufficient-evidence — distinct
  from an error.
- The **login screen** is intentionally chrome-free — no nav rail, no topbar — since it's a
  pre-authentication entry point, not a page within the app shell. Every other view (including
  Account/Settings) lives inside the standard app-shell/nav-rail composition.
