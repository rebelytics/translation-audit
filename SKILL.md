---
name: translation-audit
description: End-to-end methodology for auditing translation quality on multilingual websites — meta titles, H1s, meta descriptions, and full body content across all language versions. Includes URL discovery from XML sitemaps, user-driven prioritisation (GSC, GA4, internal weights), batched workflow, three-list state management (open → audited → verified), and a structured error taxonomy that lets non-native reviewers flag issues without overclaiming. Load this skill whenever the user mentions translation audit, translation review, localisation audit, L10n review, multilingual content quality, "translation issues on our site", "review the German/French/Spanish version", or wants to set up or extend a structured translation review project that scales beyond what one person can review in a sitting. Also load when reviewing translation quality across multiple language versions of an e-commerce, SaaS, or content site, or when continuing an in-progress audit (URLs to fetch, batches to process, fixes to verify).
---

# Translation Audit — methodology and workflow

**Created by Eoghan Henn / [rebelytics.com](https://rebelytics.com)**

Methodology for auditing translation quality across multilingual websites at
scale. Designed for projects where a single reviewer can't audit every page
in a sitting — the workflow batches URLs, persists state between sessions,
and lets non-native reviewers contribute credibly by flagging rather than
asserting.

**Licence:** This skill is released under the
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
licence. You are free to share and adapt this skill for any purpose,
provided you give appropriate credit to the original author.

**Feedback & Support:** If you encounter questions about the methodology, or
have constructive feedback about any output derived from this skill, please
open an issue on the skill's
[GitHub repository](https://github.com/rebelytics/translation-audit). This
keeps feedback public and discoverable. For direct contact, the skill's
creator can also be reached via [rebelytics.com](https://rebelytics.com).

If feedback appears to stem from this skill's methodology, log it for the
user and suggest they share it via GitHub Issues. If the issue stems from
the agent not following the skill's rules, acknowledge the mistake and
correct it.

---

## Conventions

`[workspace folder]` refers to the user's persistent workspace directory —
the place where files survive between sessions. In Cowork, this is the
folder selected at session start. In Claude Code, this is the project root.
In other systems, it's the equivalent local working directory. All file
paths in this skill resolve relative to that location.

`[project folder]` refers to the active audit project, typically
`[workspace folder]/translation-audit/`. A single workspace can contain
multiple audit projects in sibling folders (e.g., one per client or domain).

The executing AI is referred to as "the agent" throughout this skill,
because the methodology is agent-agnostic.

---

## The two principles that anchor everything

### 1. Flag, don't assert

A non-native reviewer cannot credibly assert that a translation is wrong.
They *can* flag patterns that look off and let a native speaker decide.
This is the central methodology of the skill. Every finding lands in one
of two buckets:

- **Likely errors** — unambiguous patterns even a non-native reviewer
  can call: grammar agreement violations, missing diacritics, typos,
  cross-language contamination, placeholder text, body excerpts in
  metas, broken/truncated sentences, untranslated source-language text,
  encoded HTML entities, content mismatch with the source-language
  page.
- **Worth checking** — things that look off but could be deliberate
  translator choices: register, idiom literalness, anglicism,
  cultural adaptation, brand-voice consistency, intentional informality.

If a finding could plausibly be intentional, it goes in **Worth
checking** with a "could be deliberate" hedge. When in doubt, hedge.
Overclaiming destroys the audit's credibility with the people who
actually have to act on it.

**Absence findings are high-stakes — verify before banking.** "Not found
by my query" ≠ "not present on the page." A structural-markup absence claim
("this site has no hreflang", "no canonical", "no alternate links") is
exactly the kind of confident statement that lands in a client deliverable
and is cheap to get wrong:

- **Match HTML attributes case-insensitively.** HTML attributes are
  case-insensitive, but React/Next.js/Vue emit camelCase DOM attributes —
  `hrefLang`, `crossOrigin`, `charSet`. A `hreflang="` (lowercase) regex
  returns 0 matches on a JSX-rendered site that actually has correct
  hreflang, which Google reads fine. Always use case-insensitive matching
  (`(?i)`) when grepping markup for attributes.
- **Confirm any "X is missing entirely" finding with a second method**
  before reporting it — a different regex, the rendered DOM, or a fetch via
  another tool. A single case-sensitive grep is not enough to assert a
  structural feature is missing.

**Flag the anomaly, not the remedy.** A finding points at what looks
wrong — it does not prescribe the fix or assert the consequence. Name
the anomaly and stop:

- **No prescribed remedy.** Don't write "should be X." The correct fix
  often needs domain knowledge the audit doesn't have, and a confident-
  but-wrong prescription destroys credibility faster than anything else.
  (A meta description with a stray `<br>` is the example that bit us:
  "should be a normal line break" was wrong — line breaks in a meta do
  nothing — when the only defensible statement was "there's a literal
  `<br>` here.")
- **No asserted impact.** Don't claim "breaks Y" or "shows as Z in
  search" unless it's actually been verified. You usually don't know
  how a string renders downstream.
- **Don't state the obvious.** If the excerpt makes the problem
  self-evident — an English string on a localised page is visibly
  untranslated; a misspelt word is visibly misspelt — the reader can
  see it. Don't narrate it.

Most findings need one short sentence; many need nothing beyond the
excerpt. Verbose, presumptuous diagnoses are the single biggest thing
that makes a deliverable read as junior.

### 2. Three lists, one direction

State management is built on three CSV files that record where each URL
is in the audit lifecycle. URLs move in one direction through the
pipeline, and the active state of the project is always knowable from
the three files alone:

```
open.csv          →  audited.csv          →  verified.csv
(in queue,           (findings recorded,       (fixes confirmed
 not yet audited)     awaiting client action)   live)
```

A fourth file, `excluded.csv`, holds URLs deliberately removed from
audit scope (with a reason — e.g., "not in target market", "thin
duplicate", "redirects to non-localised page"). These never move.

Every operation that changes a URL's state must update the CSVs
atomically — move the row from one file to another, never duplicate
it. The agent must read the current state of all three files at the
start of every operation; it never relies on a cached view of which
URLs are where.

---

## Project layout

The skill creates and maintains this structure inside `[project folder]`:

```
translation-audit/
├── config.yml                          # source lang, target langs, batch
│                                       # size, sitemap URL(s), output format
├── README.md                           # at-a-glance project state
├── urls/
│   ├── open.csv                        # in queue, not yet audited
│   ├── audited.csv                     # findings recorded
│   ├── verified.csv                    # fixes confirmed live
│   └── excluded.csv                    # deliberately skipped (with reason)
├── prioritisation/
│   ├── inputs/                         # raw GSC/GA4/etc. files user uploads
│   └── notes.md                        # how the priority score was built
├── data/
│   └── pages-{lang}-batch-N.json       # cached live-page content per batch
└── findings/
    ├── raw/
    │   └── batch-NN.json               # canonical findings JSON
    │                                   # (input to build_audit_doc.py;
    │                                   #  carries review_status state)
    ├── audit-YYYY-MM-DD-batch-NN.html  # reviewer-facing deliverable (tabs per language)
    ├── audit-YYYY-MM-DD-batch-NN.md    # markdown mirror for version control
    └── audit-YYYY-MM-DD-batch-NN.docx  # only when --format docx is requested
```

The split between `findings/raw/batch-NN.json` and the rendered
`audit-*.html` / `.md` is deliberate: the JSON is the data store and
carries the post-review `review_status` state once that's captured;
the `.html` / `.md` are reviewer-facing renders that deliberately
omit verdict state (see Phase 5). The `.html` is the primary
deliverable — a self-contained, zero-dependency report with one tab
per language (prints cleanly to PDF for a client hand-off). The
`.docx` is opt-in for clients who require Word.

All file paths in this skill resolve relative to `[project folder]`. The
project folder name (`translation-audit/`) can be overridden in
`config.yml` if the user wants per-domain folders (`brand-a-audit/`,
`brand-b-audit/`) inside the same workspace.

---

## The six phases (plus a native-review bridge)

The workflow has six numbered phases plus a Phase 5.5 native-review
triage step that bridges flagging (Phase 5) and verification
(Phase 6). Each is callable independently — a session can resume at
any phase based on project state. The agent should always check the
project state (read all three URL CSVs, read `config.yml`) before
deciding what phase to run.

```
1. Setup       →  2. Discover  →  3. Prioritise  →
4. Fetch       →  5. Audit     →  5.5 Triage     →  6. Verify
                                                          │
                                                          └─→ (loop back to 4 for next batch)
```

---

## Phase 1 — Setup

Run once at the start of a project. Creates the project layout and
captures configuration.

Ask the user for:

1. **Project name** (defaults to `translation-audit`). Used as the
   folder name under `[workspace folder]`.
2. **Source language** — the language treated as the source of truth for
   comparisons. Usually English; sometimes Dutch, German, or another
   language depending on the site's origin. ISO 639-1 codes (e.g., `en`,
   `nl`, `de`).
3. **Target languages** — the languages to audit. ISO 639-1 or
   locale codes (e.g., `de`, `fr-CA`, `pt-BR`).
4. **Sitemap URL(s)** — one or more URLs. If unsure, suggest
   `[domain]/sitemap.xml` and verify it resolves. For multilingual sites
   the sitemap may be a single index pointing to per-language sitemaps,
   one sitemap per language version, or a single sitemap with hreflang
   annotations on each URL entry. The skill handles all three (see
   Phase 2).
5. **Default batch size** — how many URLs to fetch and audit per pass.
   Default: 20 for full audits (meta + body), 50 for meta-only mode.
   Body audits are heavier per URL; smaller batches keep findings docs
   tractable for human review.
6. **Output format** — `html+md` (default), `html`, `md`, or `docx`.
   The **HTML** is the primary deliverable: a self-contained,
   zero-dependency report with one tab per language that prints cleanly
   to PDF for a client hand-off. The `.md` is the version-controllable
   mirror. `.docx` is opt-in for clients who require Word (needs
   python-docx).

Write the answers to `config.yml`. Create the empty CSVs with their
canonical headers (see Phase 2 for the schema). Create `README.md` with
the project name, the URL counts (initially zero), and the last-modified
timestamp.

If `config.yml` already exists, do not overwrite — read it, surface what's
there, and ask the user only about anything missing or that they want to
change.

---

## Phase 2 — Discover URLs from sitemap

Fetch the sitemap(s) and populate `open.csv`. Use the bundled script
`scripts/fetch_sitemap.py` (see Bundled scripts below). The script
handles the three common sitemap shapes:

- **Single sitemap** with all URLs (often used by smaller sites).
- **Sitemap index** pointing to per-section or per-language sitemaps
  (followed recursively, one level deep by default).
- **Multilingual sitemap with hreflang** — one URL entry per canonical
  page, with `<xhtml:link rel="alternate" hreflang=...>` siblings
  enumerating the language alternates.

For multilingual sites without hreflang in the sitemap — the common
PrestaShop / Magento "separate ccTLD or domain per language" setup —
`fetch_sitemap.py` will return zero useful rows because it cannot
infer pairing from the sitemap alone. The fallback is the bundled
`scripts/build_mapping.py`: it walks the source-language pages, reads
the on-page `<link rel="alternate" hreflang>` blocks, and emits both
`data/url-mapping.json` and `urls/open.csv` (target rows with
`canonical_url` pointing at the source page). It accepts a source
sitemap, an explicit list of source URLs, or a CSV of source URLs.

Run it whenever `fetch_sitemap.py` produces an empty `open.csv` and
the site keeps each language on its own host. The two scripts are
otherwise interchangeable downstream of Phase 2.

### Source-language regional variants — pick a canonical source

Many sites expose multiple regional variants of the source language
(e.g., `en`, `en-GB`, `en-US`). A naive "normalise locale codes and
last-wins" strategy silently picks an arbitrary regional variant
(often `en-US`) as the source-of-truth URL for comparison — even when
the international `en` / `x-default` page is what should be compared
against.

**Pairing rule for source-language alternates.** When multiple
hreflang alternates normalise to the same base source-language code,
the canonical source URL is chosen in this priority order:

1. The sitemap `<loc>` value, when it matches the source language.
2. The `x-default` alternate, when present.
3. The bare base code (e.g., `en`) without a region suffix.
4. Last resort: a region-suffixed variant, with the choice logged in
   `prioritisation/notes.md` so the user can override.

This applies to the URL stored in `canonical_url` on every non-source
row in `open.csv`, and to any URL fetched as the comparison source in
Phase 4.

### Target-side regional variants — keep distinct

The source-pairing rule above is safe for picking one source-of-truth
URL. The same normalisation is **unsafe** on the target side, where
regional variants resolve to different audit subjects. If a site
exposes `nl-NL` (`.nl`) and `nl-BE` (`.be`) as separate market sites,
collapsing both to base `nl` silently picks one and drops the other —
half the audit goes missing.

Both `fetch_sitemap.py` and `build_mapping.py` keep regional variants
distinct in `data/url-mapping.json` by storing the full hreflang code
(`nl-NL`, `nl-BE`) as the mapping key. When the audit queue needs one
URL per base language, the home-region heuristic picks the variant
whose region matches the base code (`nl` → `nl-NL`, `fr` → `fr-FR`),
and the choice is reported on stderr so nothing is picked silently.
The `--prefer-region` flag overrides per code (e.g. `nl=BE` to audit
the Belgian Dutch site instead). To audit both regional variants of a
target language, run two passes with different `--prefer-region`
choices into sibling project folders, or extend the target-list to
include the full locale codes.

### Do not enqueue the source language as audit targets

Source-language URLs are comparison references, held via
`canonical_url` / `url-mapping.json` — they are **not** audit targets
themselves. `fetch_sitemap.py` should not produce `open.csv` rows for
the source language by default; doing so doubles the queue with
non-target pages that have no source pair (e.g., 6,788 `en` rows next
to 6,788 `de` rows on a multilingual site where English is the
source).

If the user genuinely wants to audit the source language for
self-consistency (typos, broken links), they can opt in explicitly
via a config flag — but the default behaviour is to keep source-
language URLs in the mapping only, not in the audit queue.

### `open.csv` schema

| column | description |
|---|---|
| `url` | The full URL of the page. |
| `language` | ISO code matching `config.yml`. |
| `canonical_url` | URL of the source-language equivalent (or `url` itself if this is the source language). |
| `page_type` | Optional. Filled by the user or by a page-type classifier. Used in prioritisation. |
| `priority_score` | Filled in Phase 3. Empty after discovery. |
| `notes` | Free-text, optional. |

If the discovered URL count exceeds 10,000, warn the user before
writing. Very large sites need a different prioritisation strategy
(start with page types, then drill down) and may need crawl-based
discovery rather than sitemap-based.

---

## Phase 3 — Prioritise the queue

Sort `open.csv` so the most important URLs get audited first. Ask the
user what prioritisation data they have available:

- **GSC clicks/impressions** (CSV export from Search Console)
- **GA4 sessions or revenue** (CSV export from GA4 explorations)
- **Internal page-type weights** (e.g., "product pages first, then
  category pages, then content pages, then legal")
- **Commercial value tags** (e.g., a list of revenue-critical URLs)
- **Existing audit history** (re-audit verified pages every N months
  to catch regressions)
- **Manual priority list** (URLs the user already knows are problems)

The user uploads whatever they have into `prioritisation/inputs/`. The
agent reads each file, normalises it (URL + metric), and applies a
weighted score per URL. Defaults:

- Page-type weight (configured per project): primary contributor
- Traffic signal (GSC clicks, falling back to impressions, falling back
  to GA4 sessions): secondary contributor
- Commercial tag (if present): boost (e.g., 2× score)

Write the rationale to `prioritisation/notes.md` — every project ends
up with a slightly different weighting, and the next session needs to
know what was decided and why. Write the per-URL scores back to
`open.csv` and re-sort the file by descending score.

If the user has no prioritisation data, sort by page type using sensible
defaults (commercial > content > legal) and tell the user the audit
will still work but coverage of high-traffic pages is best-effort.

---

## Phase 4 — Fetch live page content

For the next batch of N URLs from the top of `open.csv` (N from
`config.yml`), fetch the live page content. Use the bundled script
`scripts/fetch_pages.py`.

For each URL the script captures:

| field | source |
|---|---|
| `url` | The URL itself (after any redirects). |
| `final_url` | The post-redirect URL if different from the requested one. |
| `status` | HTTP status code. |
| `title` | Contents of `<title>`. |
| `meta_description` | Contents of `<meta name="description">`. |
| `h1` | Text of the first `<h1>` in the document. |
| `body_text` | Visible text from `<main>` or `<article>` if present, otherwise the body with `<header>`, `<footer>`, `<nav>`, `<aside>`, and `<script>/<style>` removed. Normalised whitespace. |
| `lang_attr` | The `lang` attribute on `<html>`. |

For each non-source-language URL, also fetch its source-language
equivalent (from `canonical_url` in `open.csv` or from the URL mapping
built in Phase 2). The pair is what enables source-vs-target
comparison in Phase 5.

Write results to `data/pages-{lang}-batch-N.json`. The file holds an
array of objects, one per URL. Skip URLs that returned non-200 status —
log them with the status code so the user can decide whether to retry,
exclude, or treat the redirect target as the actual audit target.

If direct HTTP access is unavailable (sandboxed environment, blocked
domains, JS-rendered content), the skill recommends three fallbacks
in order: a browser-based fetch from inside the agent's environment, a
local Screaming Frog crawl exported to CSV and converted, or any
commercial crawler that exports the standard fields. The script
accepts a `--from-csv` mode that bypasses the fetch and reads
pre-extracted page content from a CSV in the standard schema, so the
methodology still works when the agent can't fetch directly.

### Priority order — visible content + user-facing metadata first

A translation audit is about what users actually encounter — visible
on-page text and user-facing metadata (titles, meta descriptions,
which appear in search results, browser tabs, and social shares even
if they're not "on the page"). The audit deliberately prioritises
this layer over non-visible DOM content.

The priority order for content captured per URL:

1. **User-facing metadata** (always in scope): `<title>`,
   `<meta name="description">`, `<h1>`. These are user-facing in the
   SERP, browser tab, and social previews regardless of whether they
   are rendered on the page.
2. **Visible rendered body copy** (in scope): the text users actually
   see when the page renders in a browser, after CSS and JS have
   evaluated.
3. **Non-visible DOM strings** (lower priority, separate sub-type):
   `<template>` contents, `[hidden]` / `aria-hidden` elements,
   `display:none` containers, JS notification/template strings.

### Body-layer epistemic states (sub-types)

Body-layer findings carry one of three states depending on how the
excerpt was sourced. The state determines bucket assignment and how
the diagnosis is rendered in the audit doc:

| sub_type | meaning | bucket |
|---|---|---|
| _(absent)_ | Excerpt extracted from a rendered visible-text pass. The string is confirmed visible to users. | Per the error-class rule (may be Likely error). |
| `visibility_unconfirmed` | Excerpt extracted from raw HTML with no rendered confirmation. The string is present in the DOM but the agent cannot confirm whether users actually see it. | Always Worth checking. Diagnosis prefixed with "[Visibility unconfirmed — verify on rendered page]". |
| `dom_only_not_rendered` | Excerpt is in the DOM but a hidden/template container made it confirmably non-visible (raw HTML showed `<template>`, `[hidden]`, `aria-hidden`, or inline `display:none`). | Always Worth checking. Diagnosis prefixed with "[DOM-only, not rendered]". |

The skill must not collapse `visibility_unconfirmed` and
`dom_only_not_rendered` into one state. "I couldn't determine" is
distinct from "I confirmed it's hidden", and the rendered pass
(below) is what resolves the unconfirmed case up to Likely error or
down to dom_only.

### Rendered browser pass — required for the body layer when a browser is available

The cheap-HTTP path (`requests` + BeautifulSoup) is sufficient for
user-facing metadata (title, meta description, H1) — those fields are
clean on raw HTTP. For the visible body layer, raw HTML extraction
over-captures: it cannot evaluate CSS or JS, so JS-injected hidden
state, CSS-class-driven `display:none`, and other invisibility
patterns are indistinguishable from visible body text.

The skill therefore puts a conditional gate on the body layer, keyed
to `audit_scope` in `config.yml`:

- **`audit_scope: meta_only`** — the rendered pass is never required.
  Title, meta description, and H1 are reliably captured by the raw
  HTTP fetch.
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

---

## Phase 5 — Audit per language

This is the core of the skill. For each URL in the current batch, the
agent compares the target-language page content against the
source-language equivalent and against the error taxonomy, then writes
findings to the audit doc.

### Per-URL pass

For each URL in the batch:

1. **Read the target-language page** (title, H1, meta description, body
   text) from the cached JSON.
2. **Read the source-language equivalent** from the cached JSON.
3. **Apply each error class from the taxonomy** (see Error taxonomy
   below; full detail in `references/error-taxonomy.md`).
4. **Classify each finding** as Likely error or Worth checking using
   the rule in Principle 1. Default to Worth checking when in doubt.
5. **Record the finding** with: URL, field affected (`title` / `h1` /
   `meta_description` / `body`), the exact text or excerpt, a **terse
   diagnosis** (name the anomaly only — per Principle 1: no prescribed
   remedy, no asserted impact, nothing the excerpt already makes
   obvious; many findings need no diagnosis at all), and (for body
   findings) the `sub_type`. Include `source_excerpt` **only** when the
   finding is a genuine source-vs-target divergence the reader needs
   both sides of (content mismatch, a changed claim) — omit it when the
   excerpt is self-evident (an untranslated English string, a typo, a
   stray tag), where repeating the near-identical source just adds
   noise. When one root issue spans several elements of the *same page
   in the same language* (e.g. title + meta + H1 all left in English),
   give them a shared `issue_group` key so they render as one card
   instead of repeating the diagnosis per element. Reserve
   `review_status`, `review_note`, and `reviewer` for post-review via
   `apply_verdicts.py` (default `unreviewed` / `null` / `null`).
6. **For body-layer findings sourced from raw HTML**, set the
   `sub_type` per Phase 4's epistemic state table:
   `dom_only_not_rendered` when the excerpt came from a confirmed-
   hidden container, `visibility_unconfirmed` when raw HTML was used
   without a rendered cross-check. Both states downgrade the finding
   to Worth checking and carry a diagnostic prefix in the rendered
   doc. The audit never emits a body finding as Likely error without
   confirmed visibility.

For body-copy findings, keep excerpts short — one to three sentences
around the issue, with the URL link so the native reviewer can see
the full context on the live page. A body audit is not a re-translation
pass; it's a flagging pass. If a page's body has more than ~10 candidate
findings, narrow to the most impactful and note that further review
may be warranted rather than listing every minor flaw.

### Scaling the audit across locales

A full audit — every locale × every page type — is too large for one
pass. Fan it out: **one agent per language**, each reading only its
cached `data/pages-{lang}-batch-N.json` and emitting that language's
findings. Languages are independent, so this parallelises cleanly (e.g.
via a workflow of per-language agents).

Subagents can fabricate or paraphrase excerpts, so the fan-out is only
safe behind a **mandatory central verification gate**: after the agents
return, check that **every finding's `excerpt` is a verbatim substring
of the cached field it claims** (`title` / `meta_description` / `h1` /
`body_text`, and the nested `source_pair` for `source_excerpt`). Drop
any finding that doesn't match — this is what turns "trust the agent"
into "verify against source data," and it is not optional. Re-state the
diagnosis rules (no "should be", no impact claims, terse) in the agent
contract and post-scan the merged findings for slips. Breadth matters
too: auditing *all* page types — not just core commercial pages — is
what surfaces page-type-level gaps (e.g. author or wiki templates left
untranslated across every market).

### Per-language section structure

After auditing all URLs in the batch, produce the audit doc grouped
by target language — in the HTML deliverable each language is its own
**tab**, so a section can be handed to that market's reviewer on its
own. Within a language, items split into **Likely errors** and **Worth
checking**, and findings that share an `issue_group` collapse into one
card (diagnosis stated once, each affected element listed beneath it):

```
[Language name] ([code])

Likely errors
  • [terse diagnosis — the anomaly, nothing more]
       Title             — [URL]   "[exact excerpt]"
       Meta description  — [URL]   "[exact excerpt]"
  • [terse diagnosis]
       Meta description  — [URL]   "[exact excerpt]"

Worth checking
  • [terse diagnosis] (could be deliberate)
       H1                — [URL]   "[exact excerpt]"
```

Repetition **across** languages is fine — each tab stands alone, so the
same one-line diagnosis appearing in several language tabs is expected.
Repetition **within** a language (the same block restated for title,
meta and H1 of one page) is what `issue_group` removes.

**A grouped card's headline must be true of every item under it.** When an
`issue_group` bundles several findings, set a group-level `issue_title` that
describes the whole block (e.g. "Several English strings left untranslated on
the author page") — don't let the card inherit only the first finding's
diagnosis, which fits just one item. Group **only same-theme** findings: if a
group would mix distinct issue types (a missing-diacritic H1 *and* a duplicated
brand token), split them into separate cards instead. `build_audit_doc.py` uses
`issue_title` as the card headline when present, else the first finding's
diagnosis.

"Each tab stands alone" cuts both ways: it not only *permits* cross-language
repetition, it **requires** it. A defect present in several languages'
equivalent field must be emitted in **every** affected language tab — never
consolidated onto the source tab or one tab. `issue_group` de-dupes strictly
**within** a language; it does **not** propagate a recurring defect across
languages, so that propagation is your responsibility. Example: a "TCP lll"
defect (three lowercase L's instead of Roman "III") in the title of the EN
source and the DE/ES/IT/NL/PT versions must appear as a finding in each of
those tabs — a reviewer for one market only opens their own tab, so a defect
logged elsewhere is invisible to them. **Per-finding pre-flight check:** does
this same defect appear in other languages' equivalent field? If so, emit it
there too.

If a language has no Likely errors, omit that subsection rather than
leaving it empty. Same for Worth checking. If a language has no
findings at all, the section reads `No issues flagged in this batch.`
— this is a useful signal in itself, and requires the language to
appear in `audited_languages` (below) even if zero findings reference
it. Coverage (what was checked) and findings (what was wrong) are
reported independently.

**Show coverage at the URL level, not just the language level.** A
language-level "audited" flag is not enough — a reader still can't tell
WHICH pages were checked, so "No issues flagged" reads as "maybe nothing
was looked at." Each language section must include a **Pages checked** list
of the audited URLs:

```
Pages checked
  • [URL]
  • [URL]
```

For a clean language this is the whole section under the
`No issues flagged in this batch.` line; for a language with findings, list
the checked-but-clean URLs too, so the examined set is fully visible. An
audit deliverable should make coverage legible, not just defects — "no
issues" is only trustworthy when the reader can see the examined set.

### Findings JSON and `audited_languages`

The audit phase writes the raw findings to
`findings/raw/batch-NN.json` with this shape:

```json
{
  "project_name": "...",
  "audit_date": "YYYY-MM-DD",
  "batch_number": N,
  "source_language": "en",
  "audited_languages": ["de", "fr", "es"],
  "coverage": {
    "de": ["https://…/de/page-a", "https://…/de/page-b"],
    "fr": ["https://…/fr/page-a"],
    "es": ["https://…/es/page-a"]
  },
  "findings": [ ... ]
}
```

The `audited_languages` array is **load-bearing**. Without it,
`build_audit_doc.py` groups by the languages that appear in the
findings array — and a language audited with zero findings disappears
from the deliverable, getting misread as "not checked" instead of
"checked, clean". Always populate it with every language touched in
the batch.

The `coverage` map carries the **per-language set of audited URLs** that
the deliverable's "Pages checked" list renders from — what turns a clean
language from an unsupported "No issues" into evidence of work performed.
Populate it for every audited language, clean or not. (`build_audit_doc.py`
must render a "Pages checked" list per language from this map; the SKILL
documents the behaviour, the script change lives in `scripts/`.)

Each finding object carries `language`, `url`, `field`, `excerpt`,
`diagnosis`, `bucket`, plus optional `source_excerpt`, `sub_type`,
`issue_group` (collapse-into-one-card key, scoped per language), and
`highlight` (a substring of the excerpt to mark in the HTML). The full
per-finding shape is documented at the top of `build_audit_doc.py`.

### Output

Write the reviewer-facing deliverable with the bundled script
`scripts/build_audit_doc.py`, which renders from the raw findings JSON:

- `findings/audit-YYYY-MM-DD-batch-NN.html` — **primary**. A
  self-contained report (inline CSS/JS, no dependencies) with a summary
  header, one **tab per language**, colour-coded Likely / Worth
  buckets, and grouped issue cards. Opens in any browser; print to PDF
  for a client hand-off.
- `findings/audit-YYYY-MM-DD-batch-NN.md` — version-controllable mirror.
- `findings/audit-YYYY-MM-DD-batch-NN.docx` — only with `--format docx`
  (requires python-docx).

Default output is `html,md`. The script emits a "No issues flagged in
this batch." line for any clean `audited_languages` entry, collapses
findings that share an `issue_group` into one card, and escapes
excerpts so literal markup (a stray `<br>`, an `&amp;`) shows verbatim
instead of rendering.

The deliverable **must not** show verdict tags or review attribution.
The audit doc is INPUT to native review, not OUTPUT of it (see
Phase 5.5 — Post-review triage).

### Move audited URLs

Once the audit doc is written, move each URL from `open.csv` to
`audited.csv` using `scripts/state.py move`. The script keeps the
canonical column schema (per the asset templates), handles the
atomic read-filter-write-append, and surfaces any URL it couldn't
find in the source list. Example:

```bash
python scripts/state.py move \
    --project-dir [project folder] \
    --from open --to audited \
    --urls-file batch-01-urls.txt \
    --add audit_date=YYYY-MM-DD \
    --add audit_file=findings/audit-YYYY-MM-DD-batch-NN.docx \
    --regen-readme
```

Hand-rolling the CSV moves is what causes the schema to drift away
from the templates (missing `verify_attempts`, missing `excluded_date`,
etc.). Always use `state.py`.

---

## Phase 5.5 — Post-review triage

The audit doc is the **input** to native review, not the output of
it. A native speaker reads the deliverable, decides which findings
are real errors and which are deliberate translator choices, and
those decisions get recorded in the findings JSON for downstream use
(typically a fix list for the dev team that's separate from the
audit deliverable itself).

### The audit doc must not attribute the agent's judgments to a native reviewer

The most important rule in this phase is what the audit doc must
**not** do: it must not show "Confirmed by native review" tags,
"Dismissed by native review" subsections, or any other framing that
attributes the agent's own judgments to a human expert who has not
seen the document yet. The doc is questions for the native speaker,
not verdicts from them. Anything that reads otherwise launders the
agent's flagging into a native speaker's assertion under borrowed
authority — which violates the central "flag, don't assert" rule
and erodes trust the moment the native reader spots a tag they
didn't apply.

This is enforced in `build_audit_doc.py`: the script reads the
findings JSON but **never** renders `review_status`, `review_note`,
or `reviewer` into the deliverable. Those fields are data, not
display copy.

### Review-status fields on the findings JSON

Each finding carries three optional fields that capture the
post-review state:

| field | meaning |
|---|---|
| `review_status` | `unreviewed` (default) / `confirmed` / `dismissed` / `edited`. |
| `review_note` | Free-text rationale (or the native speaker's edit, when status is `edited`). |
| `reviewer` | `native_speaker` once a human reviews. `null` while the finding is unreviewed. Distinguishes a native verdict from an agent's own classification. |

These fields are set by `scripts/apply_verdicts.py`, which takes a
verdict CSV the reviewer fills in (one row per finding, schema:
`url, field, excerpt, review_status, review_note`) and merges it
into the findings JSON. The script sets `reviewer: native_speaker`
automatically — it is the dedicated path for capturing human review,
not agent judgments.

### Two equally valid capture paths

- **Verdict CSV → `apply_verdicts.py`** — the canonical path. The
  reviewer fills in the CSV, the script merges it. Disambiguates
  matching by `(url, field, excerpt)` and reports rows that didn't
  match.
- **Direct JSON edit** — for reviewers comfortable with JSON, the
  same three fields can be set by hand. The schema is the same.

Doc-side annotation (e.g., inline tags in Word) is not currently
supported by the bundled scripts; a future iteration could add an
annotation extractor.

### What happens after verdicts are captured

The findings JSON now carries the review state. Three things follow:

1. The **fix list** for the dev team is the set of findings with
   `review_status: confirmed` (plus `edited` items, with the edit
   noted). This is a separate artefact from the audit doc — a future
   `build_fix_list.py` may render it. Until then, the agent can
   summarise the confirmed items into a fresh document or message
   when the dev team needs the deliverable.
2. **Dismissed items leave the actionable output.** A dismissed
   finding stays in the findings JSON for the record, but it does
   not appear in the fix list and is not a target of Phase 6
   verification. There is no "Dismissed" section in the reviewer-
   facing audit doc — dismissals are private to the JSON.
3. **Phase 6 verifies only the confirmed set.** If a URL has no
   confirmed findings, Phase 6 has nothing to verify for it; the URL
   can move directly to `verified.csv` (with a note that no fix was
   needed) or stay in `audited.csv` if the review is incomplete.

### Bridge to Phase 6

Phase 6 verifies that the **confirmed** set has been deployed live.
Dismissed items are out of scope for Phase 6 by definition. If a
fix is verified, the URL moves to `verified.csv` with a reference to
the confirmed set; otherwise it stays in `audited.csv` with the same
lifecycle as before. Use `scripts/state.py move` for these
transitions.

---

## Phase 6 — Verify fixes

When the client confirms that fixes for an audit batch have been
deployed, the agent verifies them and moves URLs from `audited.csv` to
`verified.csv`.

For each URL in the verification set:

1. Re-fetch the live page (same script as Phase 4).
2. Compare against the findings recorded for that URL in the audit
   doc.
3. Classify:
   - **Verified** — the flagged text is gone or has been corrected to
     match the diagnosis. Move to `verified.csv` with a `verified_date`
     column and a reference to the audit file.
   - **Not fixed** — the flagged text is unchanged. Leave in
     `audited.csv` and add a `verify_attempts` counter. Optionally
     re-audit on the next batch run.
   - **Changed but new issue** — the flagged text was edited but the
     edit introduced a different problem. Move back to `open.csv` with
     a `notes` column referencing the previous audit and the new
     concern, so the next batch audits it fresh.

Verification re-fetches always go through the same script as Phase 4,
so the agent never reasons about live state from cached data. Use
`scripts/state.py move` for the `audited → verified` and `audited →
open` transitions; the script handles the schema and regenerates
`README.md` automatically when `--regen-readme` is passed.

---

## Error taxonomy (summary)

Full taxonomy with worked examples lives in
`references/error-taxonomy.md` — read it before the first audit on
any new project. The summary below names the error classes the agent
should check for, grouped by bucket:

### Likely errors (assertable without native fluency)

- **Grammar agreement violations** — gender, number, case mismatches
  visible from the surface text (e.g., article/noun disagreement).
- **Missing or wrong diacritics** — letters missing accents/umlauts
  that the language requires; or accents from a different language
  family.
- **Typos** — character-level errors visible by spell-check or
  cross-comparison with the same word elsewhere on the site.
- **Cross-language contamination** — words from a different language
  appearing in the target text (e.g., Spanish words on a Catalan page).
- **Placeholder text** — meta descriptions that just repeat the page
  title, generic "Disclaimer" text on policy pages, untranslated
  template strings.
- **Body-excerpt-in-meta** — meta description is a sentence pulled from
  the middle of the article body, not a summary (refers to "the
  methods above" with no methods visible).
- **Truncated or broken sentences** — text ending mid-clause,
  punctuation errors, double negation.
- **Untranslated source-language text** — English (or source-language)
  strings on a localised page where every other comparable page is
  translated.
- **Encoded HTML entities in visible text** — `&amp;`, `&#039;`, etc.
  showing through as literal characters in the rendered page.
- **Content mismatch with source** — the target page makes a different
  claim from the source page (e.g., source says "fastest-growing
  manufacturer", target says "manufacturer of fast-growing products").
- **Title/H1 inconsistency on the same page** — different wording,
  spelling, or casing between the two on a single URL.

### Worth checking (translator judgment needed)

- **Register or formality** — formal vs informal address mixed across
  pages.
- **Idiom literalness** — literal renderings of source-language idioms
  that read awkwardly in the target language.
- **Anglicism choice** — English terms left untranslated where local
  alternatives exist.
- **Cultural adaptation** — references that don't carry across markets.
- **Brand voice consistency** — tone shifts between pages, sections, or
  product categories.
- **Title case vs sentence case** — capitalisation conventions that
  differ from the language's norms.

For each class, `references/error-taxonomy.md` includes one or more
worked examples, the diagnostic pattern to look for, and the
bucket-assignment rule (when the same class can be either bucket
depending on context).

---

## Bundled scripts

The scripts in `scripts/`:

- **`fetch_sitemap.py`** (Phase 2) — fetches one or more sitemaps and
  writes `open.csv`. Handles sitemap indexes, hreflang annotations, and
  per-language sitemaps. Applies the source-language pairing rule and
  keeps target-side regional variants distinct (home-region
  heuristic, `--prefer-region` override). Excludes source-language
  URLs from `open.csv` by default; use `--include-source` to opt in.
- **`build_mapping.py`** (Phase 2 fallback) — for sites where each
  language lives on its own ccTLD/domain and the per-shop sitemaps
  carry no hreflang. Walks the source-language pages, reads on-page
  `<link rel="alternate" hreflang>`, and emits both
  `data/url-mapping.json` and `urls/open.csv` (target rows with
  `canonical_url` set to the source URL). Same regional-variant
  handling as `fetch_sitemap.py`.
- **`fetch_pages.py`** (Phase 4) — fetches live page content (title,
  H1, meta description, body text, status) for a batch of URLs.
  Writes `data/pages-{lang}-batch-N.json`. Normalises whitespace
  uniformly across all extracted fields. Drops `<template>`,
  `[hidden]`, `aria-hidden`, and inline `display: none` /
  `visibility: hidden` containers before returning body text.
  Supports `--from-csv` mode to read pre-extracted content from a CSV
  instead of fetching, for use in sandboxed environments.
- **`build_audit_doc.py`** (Phase 5) — assembles the reviewer-facing
  deliverable from a findings JSON at `findings/raw/batch-NN.json`.
  Default output `html,md`: a self-contained **HTML report with one tab
  per language** (inline CSS/JS, no dependencies — the primary
  deliverable) plus a Markdown mirror; `--format docx` adds a Word file
  (needs python-docx). Renders a summary header, a "sample audit — not a
  complete crawl" scope banner, the Likely errors / Worth checking split,
  a **Pages checked** list per language (from the `coverage` map), and
  collapses findings that share an `issue_group` into one card headlined
  by `issue_title` (else the first finding's diagnosis). Prefixes
  body-layer findings by `sub_type` (`[DOM-only, not rendered]` /
  `[Visibility unconfirmed …]`), HTML-escapes excerpts so literal markup
  shows verbatim, emits "No issues flagged in this batch." for every
  clean `audited_languages` entry, and prints a footer with author
  attribution + CC BY 4.0. The deliverable **does not** show verdict
  state — see Phase 5.5.
- **`apply_verdicts.py`** (Phase 5.5) — patches the findings JSON
  with native-reviewer verdicts from a verdict CSV (`url`, `field`,
  `excerpt`, `review_status`, optional `review_note`). Sets
  `reviewer: native_speaker` automatically. Used to capture human
  review without hand-editing JSON. Does **not** regenerate the
  reviewer-facing audit doc — verdict state lives in the JSON and
  feeds downstream artefacts (e.g. a fix list), not the audit
  deliverable.
- **`state.py`** (all phases) — three-list lifecycle bookkeeping.
  Subcommands: `init` creates the four state CSVs from the asset
  templates; `move` shifts URLs between lists with atomic
  read-filter-write semantics and optional new columns (e.g.
  `audit_date`); `exclude` drops URLs to `excluded.csv` with a
  reason; `reaudit` re-queues a URL from `audited`/`verified` back to
  `open`; `status` and `validate` report counts and check schemas
  against the templates. The agent should use `state.py` rather than
  hand-rolling CSV operations — that's where schema drift creeps in.

Each script is CLI-runnable (`python scripts/<name>.py --help`) and
runs in any environment with Python 3.9+. The agent should prefer
the scripts over reimplementing the fetch/parse/build/state logic
per session.

### Dependencies

Required Python packages (mirrors `requirements.txt`):

- `requests` — HTTP fetching (`fetch_sitemap.py`, `fetch_pages.py`)
- `beautifulsoup4` — HTML parsing for page-content extraction
  (`fetch_pages.py`)
- `PyYAML` — `config.yml` parsing (all scripts)
- `python-docx` — **optional**, only for `build_audit_doc.py --format
  docx`. The default HTML + Markdown deliverables need no third-party
  packages.

Install with `pip install -r requirements.txt` as part of Phase 1
setup before running the scripts for the first time. Trusting the
prose alone without installing the requirements file produces a
`ModuleNotFoundError` at the page-fetch phase. Keep the prose
dependency list and the requirements file in sync — if one is updated,
update both.

---

## Pre-flight verification (before delivering an audit doc)

Before delivering an audit doc, the agent must re-read this skill's
rules and check the doc against them. This is a quality gate, not
overhead — every rule violation that slips through erodes the audit's
credibility with the translators who act on it. Check in order:

1. **Flag, don't assert — and stay terse.** Every finding in **Likely
   errors** is one a non-native reviewer can defend without native
   fluency (register, idiom, anglicism go in **Worth checking**).
   Diagnoses name the anomaly only — no prescribed remedy ("should be
   X"), no asserted impact, nothing the excerpt already makes obvious.
   One root issue spanning several elements of the same page+language
   uses a shared `issue_group` instead of repeating the block.
2. **Hedge by default.** Every finding in **Worth checking** ends with
   a hedge like "could be deliberate", "worth a translator review",
   or "intentional informality possible".
3. **Every finding has a URL, field, and exact excerpt.** A diagnosis
   is optional (a self-evident excerpt may need none); when present it
   is terse. The excerpt is the actual text from the page, not a
   paraphrase.
4. **Genuine source-vs-target divergences include the source excerpt**
   — a content mismatch or changed claim without the source is a guess.
   But don't pad self-evident findings (untranslated string, typo,
   stray tag) with a redundant, near-identical source line.
5. **No findings invented.** Every excerpt is a verbatim substring of
   `data/pages-{lang}-batch-N.json`. If a finding can't be traced back
   to fetched data, it doesn't go in the doc. When findings were produced
   by parallel per-language subagents, this verbatim check has been run
   centrally over **all** of them and non-matches dropped.
6. **State is consistent.** After the audit, every URL in the batch
   has been moved from `open.csv` to `audited.csv`. No URL appears in
   two CSVs at once.
7. **Source pairing is correct.** Every non-source row's
   `canonical_url` was chosen by the priority order in Phase 2 (sitemap
   `<loc>` → `x-default` → bare base code → region-suffixed). No
   source-language URLs are queued as audit targets unless the user
   explicitly opted in.
8. **Regional target variants are distinct.** No `open.csv` row
   collapses `nl-NL` and `nl-BE` (or any other regional pair) onto a
   single base code that points to the wrong host. Run
   `scripts/state.py validate` if in doubt.
9. **Body epistemic state is recorded — and verified when possible.**
   Every body finding sourced from raw HTML carries the correct
   `sub_type`: `dom_only_not_rendered` when a hidden container was
   confirmed, or `visibility_unconfirmed` when raw HTML was used without
   a rendered cross-check. A finding may **keep** `visibility_unconfirmed`
   only when no browser was available; if a browser was available it was
   resolved via the rendered check (visible → caveat cleared; hidden →
   `dom_only_not_rendered`). No body finding is in Likely errors without
   confirmed visibility.
10. **No native-reviewer attribution in the deliverable.** The
    rendered `.html` / `.md` shows no "Confirmed by native review"
    tags, no "Dismissed by native review" subsections, no reviewer
    notes. Verdict state lives in the JSON only and feeds downstream
    artefacts.
11. **`audited_languages` is populated.** The findings JSON includes
    every language touched in the batch, so clean languages still
    surface a "No issues flagged in this batch." line in the
    deliverable.
12. **Coverage is shown.** The `coverage` map is populated for every
    audited language, so each section renders a "Pages checked" list —
    a clean language shows what was examined, not a bare "No issues".
13. **Grouped cards are coherent.** Every `issue_group` card's headline
    (`issue_title`, else the first diagnosis) is true of **all** its
    instances; a group bundles only same-theme findings, and mixed-type
    groups are split into separate cards.

If any check fails, fix it before presenting the doc to the user.

---

## Quick reference

| Question | Answer |
|---|---|
| Where do new URLs go? | `urls/open.csv`, sorted by priority. |
| Where do findings go? | `findings/audit-YYYY-MM-DD-batch-N.html` (primary — tabs per language) + `.md` mirror; `.docx` only with `--format docx`. |
| When does a URL move from `open` to `audited`? | When the audit doc for its batch is written. |
| When does a URL move from `audited` to `verified`? | When the agent re-fetches it and confirms the fix is live. |
| Can a URL move backward? | Yes — `audited` → `open` if a fix introduces a new issue. |
| What's the default batch size? | 20 for full audits (meta + body), 50 for meta-only. |
| What counts as a Likely error? | A pattern a non-native reviewer can defend without native fluency. |
| What counts as Worth checking? | A pattern that could plausibly be a deliberate translator choice. |
| When in doubt? | Worth checking, with a "could be deliberate" hedge. |
| How long should a diagnosis be? | As short as possible — name the anomaly only. No "should be X", no asserted impact, nothing the excerpt already shows. Many findings need none. |
| Same issue across a page's title/meta/H1? | Give them one `issue_group` → renders as a single card, not repeated blocks. (`issue_group` is within-language only.) |
| Same defect in several languages' equivalent field? | Emit it in **every** affected language tab — repetition across tabs is required, not just allowed. `issue_group` does not propagate across languages. |
| Auditing many locales at once? | One agent per language reading its cached JSON, then a **mandatory** central check that every excerpt is a verbatim substring of the data (drop non-matches). Cover all page types, not just core pages. |
| Grouped card with several distinct items? | Give the group an `issue_title` headline true of the whole block; group only same-theme findings and split mixed-type ones into separate cards. |
| What if direct HTTP fetch is blocked? | Cloudflare JS challenge or rate-limit (403/429) defeats `requests` even with full headers — drive a real browser (navigate once to clear it, then same-origin `fetch()`), or use `fetch_pages.py --from-csv` with a Screaming Frog / browser export. |
| What if the site has no sitemap? | Fall back to a crawl (Screaming Frog, equivalent) and import the URL list via `--from-csv`. |
| Which source URL is used for comparison? | Sitemap `<loc>` → `x-default` → bare base code → region-suffixed (Phase 2). |
| Are source-language URLs in the audit queue? | No — they are comparison references via `canonical_url`, not targets. Opt in explicitly to audit them. |
| What if the body excerpt isn't visible on the page? | If a browser is available, **verify in the rendered page first** (→ visible: no caveat; → hidden: `dom_only_not_rendered`). Keep `visibility_unconfirmed` only when no browser exists at all. |
| What if the site has no hreflang in the sitemap (per-domain ccTLD setup)? | Run `scripts/build_mapping.py` instead of `fetch_sitemap.py` — it walks source pages and reads on-page hreflang. |
| What does `nl-NL` vs `nl-BE` mean for the audit? | Target-side regional variants are kept distinct. The home-region heuristic picks `nl-NL` for base `nl`; use `--prefer-region nl=BE` to audit Belgian Dutch instead. |
| Where do post-review verdicts live? | `review_status` / `review_note` / `reviewer` per finding in the findings JSON. Captured by `apply_verdicts.py` after the native speaker reviews the audit doc. |
| Does the audit doc show verdict tags? | No — by design. The audit doc is INPUT to native review, not output of it. Verdicts feed downstream artefacts (e.g. a fix list). |
| How do I move URLs between state lists? | `python scripts/state.py move --from <list> --to <list> --urls-file …`. Don't hand-roll CSV operations. |
| What is the fix list? | The set of findings with `review_status: confirmed` after native review — this is what Phase 6 verifies. |
