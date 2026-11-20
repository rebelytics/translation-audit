# Rendered verification of the body layer and h1 — translation-audit reference

Reference file for the `translation-audit` skill (CC BY 4.0 — Eoghan Henn
and contributors). Load it before auditing the body layer of any batch,
before shipping an h1 visible-composition claim, and before resolving
`visibility_unconfirmed` findings. The sections below are moved verbatim
from the skill core with their headings unchanged. A section named here (a
phase, Principle 1, a heading) is a heading of `SKILL.md`; where that
section moved, its stub there names the file that now holds it.

Load triggers: auditing the body layer of a batch; an h1 visible-composition claim; resolving visibility_unconfirmed before delivery

### Rendered browser pass — required for the body layer when a browser is available

The cheap-HTTP path (`requests` + BeautifulSoup) is sufficient for
title and meta description — those fields live outside the render
surface (SERP, browser tab), so raw capture is ground truth for them.
For the visible body layer, raw HTML extraction over-captures: it
cannot evaluate CSS or JS, so JS-injected hidden state,
CSS-class-driven `display:none`, and other invisibility patterns are
indistinguishable from visible body text.

**H1 is a rendered element — "reliably captured" is not "reliably
visible".** An H1 renders on the page, and templates routinely hide
parts of it with CSS (a duplicate artist-name span kept for a layout
variant, a screen-reader-only prefix). Raw extraction concatenates
those hidden descendants into the H1 string, producing false
"duplicated text" findings that look authoritative because both
target and source carry the same hidden markup. `fetch_pages.py`
applies its hidden-container drops inside the h1 subtree, but
CSS-class-driven hiding is undetectable from raw HTML — so any h1
finding that alleges a **visible-composition defect** (duplicated
text, leaked template string) follows the body rules: it must pass
the rendered check before it may ship as a Likely error, and it joins
the body findings in the *Resolving `visibility_unconfirmed`* pass.
H1 findings about the text itself (a typo, an untranslated heading)
are unaffected — the characters are the same rendered or not; only
composition claims need the rendered confirmation.

The skill therefore puts a conditional gate on the body layer, keyed
to `audit_scope` in `config.yml`:

- **`audit_scope: meta_only`** — the rendered pass is never required
  for title and meta description, and h1 *text* findings are fine on
  raw capture. The one exception carries over even here: an h1
  visible-composition claim (duplicated text) still needs a rendered
  check before shipping as a Likely error.
- **`audit_scope: full`** (default) — body findings **must** be
  verified against rendered output. When a browser is available a
  rendered pass is **mandatory, not optional**: prefer capturing the
  body from the rendered DOM at fetch time (e.g. Claude in Chrome
  `get_page_text`, or an iframe's `innerText`) so body findings are
  confirmed-visible by construction; otherwise, if the body was first
  taken from a raw fetch, run the rendered verification in *Resolving
  `visibility_unconfirmed`* (below) before delivery. Shipping a body
  finding with the `visibility_unconfirmed` caveat is a **last resort,
  only when no browser exists at all** — then tag every such finding
  and note in `prioritisation/notes.md` that the body ran un-rendered.

A `require_rendered_body: true` flag in `config.yml` turns the soft
gate into a hard stop — projects that want to refuse body findings
without a rendered pass can opt in.

When available, prefer a browser integration that exposes only
rendered visible text for the body layer — for example, Claude in
Chrome (`get_page_text`) when running in an environment that supports
it. Availability varies:

- **Terminal-based agent CLIs**: may require an explicit opt-in flag
  at launch or an in-session toggle. Check the CLI's documentation.
- **Desktop apps and IDE extensions**: typically available once the
  browser extension is installed and the host browser is running.
- **Some environments cannot use browser integration at all** — for
  example, third-party model providers (Bedrock / Vertex / Foundry)
  or non-Chromium browsers. In those cases the raw-HTTP fetch remains
  the fallback; body findings carry `visibility_unconfirmed` and the
  gap is noted in `prioritisation/notes.md`.

### Mitigations on the raw-HTML body path

Even when the rendered pass is unavailable, `fetch_pages.py` drops
the most obviously non-visible containers before returning body
text. The script removes:

- `<template>` subtrees entirely
- elements with the `[hidden]` attribute
- elements with `aria-hidden="true"`
- elements with inline `style="display: none"` or
  `style="visibility: hidden"`

These heuristics do not catch JS-injected hidden state or
CSS-class-driven `display: none` — those need the rendered pass.
But they materially reduce the false-positive rate on the raw-HTTP
path. Strings still surfaced after these drops, when the rendered
pass is unavailable, carry `visibility_unconfirmed` rather than
being treated as confirmed visible.

### Resolving `visibility_unconfirmed` with a rendered check

A `visibility_unconfirmed` tag is a *to-do*, not a final state. If a
browser is available, resolve it before delivery rather than shipping
the caveat to the reviewer:

1. Load the **rendered** page in the browser and confirm whether the
   flagged string is actually shown.
2. **Confirmed visible** → clear `sub_type` (the finding renders with
   no caveat, and can be a Likely error if its class warrants it).
   **Confirmed hidden** (template / `display:none`) → set
   `dom_only_not_rendered`.
3. Keep `visibility_unconfirmed` only when no rendered check is
   possible at all.

**`innerText` under-reports — cross-check before concluding "hidden".**
A string can be genuinely visible yet absent from
`document.body.innerText`: CSS-rotated or absolutely-positioned badges
(e.g. a sale ribbon), collapsed accordions, and JS-hydrated product
grids are common culprits. When `innerText` lacks a string the raw DOM
(`textContent`) contains, **take a screenshot** (or check the
element's `getBoundingClientRect` / computed style) before deciding —
don't downgrade a real, visible finding on the strength of an
`innerText` miss. The rendered check also catches raw-HTML **false
positives** — a string present in the source HTML but never rendered
(e.g. a nav label the live page drops); remove those.

### Batch-resolving at scale — the per-domain iframe harness

Navigating to every page that has body findings does not scale (a
multi-locale batch can easily have 100+ affected pages). The harness
that does: **one navigation per domain**, then a single in-page script
that loads each affected path of that domain into a same-origin
iframe and checks all of that page's excerpts in one go. Per excerpt:

1. Normalise the iframe's `document.body.innerText` the same way the
   cached `body_text` was normalised (`\s+` → single space) and test
   substring containment → **visible**.
2. On an innerText miss, find the deepest element whose `textContent`
   contains the excerpt and check its computed style and
   `getBoundingClientRect()` — display/visibility hidden in the
   ancestor chain → **hidden**; zero-size rect → treat as hidden;
   in-layout with a real rect → **visible** (this is the
   innerText-under-reports fallback from above, automated).
3. Not in the rendered DOM at all → candidate raw-HTML false positive
   (see the drift rule below before removing).

Return single-letter verdicts per excerpt, not text — tiny payloads,
and no page content flows back through the conversation. Two
implementation notes: transfer the excerpt list into the page
**base64-encoded** (it sidesteps both quote-escaping and
content-filter blocks on excerpts that happen to contain trigger
words), and remember cross-origin iframes are not DOM-readable — the
harness must run from a page on the same domain it is checking.

### Rendered capture is per-element — `innerText` falls back on unrendered elements

"Rendered capture" is only rendered if the **element** is rendered.
Per spec, `innerText` on an element that is not being rendered
silently falls back to `textContent` — it answers a different
question exactly when the element isn't in layout, which is exactly
when you were relying on it to filter hidden descendants. The classic
trap is a responsive template whose only `<h1>` is the mobile
variant: `display:none` at a desktop capture viewport, so
`h1.innerText` returns the full `textContent` — including CSS-hidden
descendants such as an artist or brand name duplicated in a product
H1 for a layout variant — and every element in the subtree reports a
0×0 rect. No wait time fixes this; it is a viewport property, not a
timing one.

Capture logic for heading fields on responsive sites:

1. **Check the element's bounding rect before trusting `innerText`.**
   A zero-size `getBoundingClientRect()` means the "rendered" read is
   `textContent` in disguise.
2. **Prefer the first `<h1>` with a non-zero rect** — the rendered
   desktop variant, when one exists.
3. **When no `<h1>` is rendered at the capture viewport** (a
   mobile-only h1 at a desktop viewport), take the first `<h1>` and
   compute its visible composition manually: walk its descendants and
   drop any with computed `display:none` / `visibility:hidden`,
   **skipping the check on the root itself** — the root's hiding is
   viewport-conditional, but its hidden descendants are hidden at
   every viewport.
4. **Record the capture viewport in the cached data** (e.g. an
   `h1_capture` note alongside the field in
   `data/pages-{lang}-batch-N.json`) so findings on responsive
   variants stay interpretable later.

The same rect-check applies inside the iframe harness above: harness
step 2 already covers `innerText` *misses* on visible content; this
rule covers the inverse failure, where `innerText` *hits* on text
that is never visible because the element it was read from isn't
rendered at the capture viewport.

### Verify close to fetch — drift on time-variant templates

A rendered verification that runs hours after the fetch doesn't just
verify — it **re-samples a moving target**. Homepage carousels,
campaign slots and product-grid hydration rotate content, so a string
that was genuinely served at fetch time can be legitimately absent at
verify time. "Not in the rendered DOM" therefore has two readings:
*never rendered* (a true raw-HTML false positive — remove) and *no
longer present* (stale — the finding was probably real). Rules:

- Run the rendered verification as close to the fetch as possible —
  ideally in the same session, before any audit agents run.
- On **time-variant surfaces** (homepage, campaign/exposure slots,
  "popular now" grids), treat a not-in-DOM verdict as
  "unverifiable — content rotated", not as proof of a false positive.
  Drop the finding from the deliverable if it can't be confirmed, but
  record the removal in `prioritisation/notes.md`; if the same defect
  pattern is confirmed on other locales, say so there, so the
  systemic pattern isn't silently lost.
- On stable surfaces (product copy, CMS/legal text), not-in-DOM is a
  genuine false-positive signal and the finding is removed outright.
