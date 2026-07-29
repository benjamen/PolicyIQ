# Connecting the UI to Real Data

Design for replacing the mockup's hardcoded content with an actual data-fetching layer, and for
how the backend's synthetic-fixture flag eventually flips to real, citation-verified data.
Design-only pass, same convention as `10-AUTH-AND-ACCOUNTS.md`.

## Current state

`site/index.html` has **zero fetch calls** — every stat tile, insurer name, citation excerpt, and
grade score is typed directly into the HTML as static text. It's explicitly a design mock, not
shippable code (`08-UI-DESIGN.md`), so this isn't a bug in the mockup, but it also means there is
no existing data-fetching pattern to extend — this doc establishes the first one.

On the backend, `POST /api/v1/compare/life` is the only endpoint that actually exists, and it
always returns `data_source: "synthetic_fixture"` (`backend/app/api/v1/compare.py:69`), sourced
from `backend/app/fixtures/sample_data.py` — explicitly throwaway data with invented insurer
names, documented for deletion once a real repository layer can hydrate `ProductProfile` objects
from crawled/extracted rows.

## Fetch-wrapper convention

Prose/pseudocode, since no JS framework exists yet — this is the pattern the eventual Vue 3
rewrite's data layer (`frontend/src/`, per `01-ARCHITECTURE.md`) should match, not a library to
adopt now:

```js
async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include", // sends the httpOnly session cookie, see 10-AUTH-AND-ACCOUNTS.md
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (res.status === 401) { redirectToLogin(); return; }
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}
```

`API_BASE` is a config value, not hardcoded — points at `localhost:8000` in local dev, an empty
string (same-origin) in production once frontend and API are colocated, and stays entirely unset
in the standalone GitHub Pages mockup (see "Live demo mode" below).

## States every data-backed view must design for

- **Loading** — skeleton placeholder matching the eventual content's shape (card outline, shimmer
  using the existing `--slate-soft`-family tokens), not a blank screen or spinner-only state.
- **Error** — fail-closed: a visible retry-able error card (`brick`-toned per the existing
  semantic-color convention), never a silently empty or stale-looking view. Matches the
  architecture's "fail closed, not open" principle (`01-ARCHITECTURE.md` design principle #3) —
  that principle applies to the UI layer, not just extraction confidence.
- **Auth** — a `401` redirects to login rather than rendering a broken/empty authenticated view.
- **Empty / insufficient evidence** — already partially modeled server-side by
  `insufficient_evidence` on the `/search` response shape (`03-API-SPEC.md`); the UI needs an
  explicit "not found in indexed documents" rendering for this, distinct from a network error.

## `data_source`: from fixture to real

`CompareResponse.data_source` is currently a plain `str` literal
(`backend/app/schemas/compare.py:44`). Forward-looking note for a later implementation slice (not
a code change in this doc): promote it to an enum, `synthetic_fixture | extracted_verified`, so
the field is a closed set a client can safely switch on rather than a string to string-compare.
UI convention: a `neutral` pill reading "Synthetic fixture data" for `synthetic_fixture` (already
present in the mockup, line 568), and an `ok`-styled "Live, citation-verified data" pill for
`extracted_verified` — same status-pill visual language the admin views already use for pipeline
health, per `08-UI-DESIGN.md`'s component notes.

## What gets real illustrative wiring vs. stays static

Only `POST /api/v1/compare/life` exists server-side today, so it's the one view that gets an
actual `fetch()` call written into the mockup as the documented integration pattern. `/search`,
`/changes`, `/admin/*` are spec'd in `03-API-SPEC.md` but unimplemented — their loading/error
states in the mockup stay static/demo-toggle-driven, clearly commented as illustrative rather than
wired to anything real.

## Live demo mode, not default-on

`site/index.html` deploys standalone to GitHub Pages with no backend colocated
(`.github/workflows/deploy-pages.yml`). A live `fetch()` firing by default would just fail/CORS-
error for every visitor to the public design preview. Convention: the real `fetch()` code is
written and visible in the mockup's `<script>` block as the reference pattern, but only runs when
the page is loaded with a `?live=1` query param pointing `API_BASE` at a configurable, locally-
running backend. The default (no query param) rendered state stays fully static — the design
preview never shows a broken network call to a visitor.
