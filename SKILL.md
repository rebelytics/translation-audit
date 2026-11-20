---
name: translation-audit
description: "End-to-end methodology for auditing translation quality on multilingual websites — meta titles, H1s, meta descriptions, and full body content across all language versions. Includes URL discovery from XML sitemaps, user-driven prioritisation (GSC, GA4, internal weights), batched workflow, three-list state management (open → audited → verified), and a structured error taxonomy that lets non-native reviewers flag issues without overclaiming. Load this skill whenever the user mentions translation audit, translation review, localisation audit, L10n review, multilingual content quality, \"translation issues on our site\", \"review the German/French/Spanish version\", or wants to set up or extend a structured translation review project. Also load when continuing an in-progress audit (URLs to fetch, batches to process, fixes to verify)."
license: CC-BY-4.0
metadata:
  author: Eoghan Henn and contributors
  source: https://github.com/rebelytics/translation-audit
  version: "1.5.0"
  core_max_lines: "861"
---

# Translation Audit — methodology and workflow

Methodology for auditing translation quality across multilingual websites at
scale. Designed for projects where a single reviewer can't audit every page
in a sitting — the workflow batches URLs, persists state between sessions,
and lets non-native reviewers contribute credibly by flagging rather than
asserting.

The shared verification rules this skill applies (the deployment gate,
emitter classification) are owned by the published open-source companion
redirect-verification (https://github.com/rebelytics/redirect-verification);
the pointers below name its § Shared verification rules.

**Licence:** This skill is released under the
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
licence. You are free to share and adapt this skill for any purpose,
provided you give appropriate credit to the original author.

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
omit verdict state (see Phase 5, Output: `references/audit-doc-output.md`). The `.html` is the primary
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

## Reference files

Episodic sections live in `references/`. Load each file when its trigger
fires: an episode run from this core alone skips the rules the file holds.
Every moved section keeps its heading here with a stub that states its
never/always rule and names its file. If an episode ran before its file was
loaded, load it and re-check that work before delivery.

| load when | file | holds |
|---|---|---|
| before the first audit on a new project | `references/error-taxonomy.md` | every error class in full |
| before Phase 2 writes `open.csv`; choosing a source URL or regional variant | `references/discovery-variants.md` | Phase 2: source pairing, regional variants, source language not enqueued |
| scripted HTTP is bot-blocked and a browser is available | `references/browser-fetch.md` | Phase 4: the browser-fetch playbook |
| before the body layer; an h1 composition claim; resolving `visibility_unconfirmed` | `references/rendered-verification.md` | Phase 4: the rendered pass through drift |
| before dispatching per-language agents or a cross-market overview | `references/scaling-across-locales.md` | Phase 5: scaling across locales |
| before building an audit doc with assertive findings | `references/claim-verification.md` | Phase 5: Stage 2 |
| before writing the findings JSON or rendering the deliverable | `references/audit-doc-output.md` | Phase 5: per-language structure, findings JSON, output |
| native-reviewer verdicts arrive | `references/post-review-triage.md` | Phase 5.5 in full |
| the client reports fixes deployed | `references/verify-fixes.md` | Phase 6 in full |
| choosing a script, first run in a project, a missing-module error | `references/bundled-scripts.md` | Bundled scripts and Dependencies |

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
`scripts/fetch_sitemap.py` (see `references/bundled-scripts.md`). The script
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

When several alternates normalise to the source language, `canonical_url`
is chosen sitemap `<loc>` → `x-default` → bare base code → region-suffixed
(logged). Load `references/discovery-variants.md` before Phase 2 writes `open.csv`.

### Target-side regional variants — keep distinct

Never collapse target regional variants (`nl-NL`, `nl-BE`) onto one base
code; the heuristic and `--prefer-region` are in `references/discovery-variants.md`.

### Do not enqueue the source language as audit targets

Source-language URLs stay in the mapping as comparison references, not in
`open.csv`, unless the user opts in (`references/discovery-variants.md`).

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

### A batch is a sample of authored content — it is not coverage

Shared rule — see `redirect-verification/SKILL.md` § Shared verification
rules (emitter classification), in the published open-source companion
redirect-verification (https://github.com/rebelytics/redirect-verification).
The instance here: everything this audit
reads — titles, metas, H1s, body copy — is **content-emitted**, authored
per document and per translation, so a batch says nothing about the URLs
outside it. The **component-emitted** strings (nav labels, footer text, a
template's boilerplate) are the samplable class, which is why
`body_text` strips header, footer and nav in Phase 4. Two rules follow.

1. **Coverage claims require enumeration, not sampling.** "The German
   product pages are clean" or "the untranslated-string issue affects
   roughly one in six articles" is only defensible over a population
   that was actually read. The deliverable's "sample audit — not a
   complete crawl" banner and the per-language **Pages checked** list
   exist so the reader sees the examined set instead of inferring
   coverage from it. Where a specific defect pattern needs sizing
   across the site — a leaked template string, an untranslated
   boilerplate block, a link to a retired host — run a targeted full
   sweep of that one pattern over the sitemap-enumerated population
   (a substring test per page, not an audit; roughly 1,500 pages
   fetch in under a minute from a same-origin tab, see the
   browser-fetch playbook in `references/browser-fetch.md`) and report per-locale counts.
2. **Each language version is read in its own right.** Translations of
   one document are independent artefacts (shared rule above), so the
   batch never infers a translation's state from its source or from a
   sibling, and the cross-language propagation check in Phase 5
   (`references/audit-doc-output.md`, Per-language section structure: emit
   the defect in every affected tab) is a check that reads the sibling
   fields, not an assumption that they match.

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

### Browser-fetch playbook for bot-blocked multi-domain sites

When scripted HTTP is bot-blocked and a browser integration exists, load
`references/browser-fetch.md` before the first navigation: CORS probe first,
never one navigation per page, no raw HTML through the conversation.

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
(`references/rendered-verification.md`) is what resolves the unconfirmed case up to Likely error or
down to dom_only.

### Rendered browser pass — required for the body layer when a browser is available

With `audit_scope: full` and a browser available, the rendered pass is
mandatory before a body finding or an h1 composition claim ships as a Likely
error. Load `references/rendered-verification.md` before auditing the body layer.

### Mitigations on the raw-HTML body path

What `fetch_pages.py` drops on the raw path, and why surviving strings carry
`visibility_unconfirmed`: `references/rendered-verification.md`.

### Resolving `visibility_unconfirmed` with a rendered check

A to-do, resolved before delivery whenever a browser exists; an `innerText`
miss alone never proves a string hidden. Steps: `references/rendered-verification.md`.

### Batch-resolving at scale — the per-domain iframe harness

Many affected pages: one navigation per domain and a same-origin iframe
harness, in `references/rendered-verification.md`.

### Rendered capture is per-element — `innerText` falls back on unrendered elements

Check an element's rect before trusting its `innerText`: an unrendered element
returns `textContent`. Capture rules: `references/rendered-verification.md`.

### Verify close to fetch — drift on time-variant templates

On time-variant surfaces a not-in-DOM verdict means content rotated, not a
false positive. Rules: `references/rendered-verification.md`.

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
   instead of repeating the diagnosis per element. If a `highlight` is
   set, it must point at its occurrence **unambiguously**: a bare
   short token ("and") is a substring of countless longer words, and a
   mis-anchored mark on a correct finding reads as a blunder — include
   disambiguating context (`, and 7` rather than `and`) whenever the
   defect token occurs anywhere else in the excerpt, even mid-word.
   Reserve `review_status`, `review_note`, and `reviewer` for
   post-review via `apply_verdicts.py` (default `unreviewed` / `null`
   / `null`).
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

Per-language agents are safe only behind the mandatory central verbatim-excerpt
gate, stated in the agent contract and negative-controlled. Load
`references/scaling-across-locales.md` before dispatching them or building an overview.

### Stage 2 — claim verification and re-bucketing (mandatory)

Every assertive finding gets one adversarial claim check before delivery.
Load `references/claim-verification.md` after the verbatim gate and the rendered
pass, before building any audit doc that carries assertive findings.

### Per-language section structure

One tab per language, Likely errors then Worth checking, plus Pages checked. A
defect in several languages is emitted in every affected tab (`issue_group` is
within-language). Load `references/audit-doc-output.md` before writing the findings JSON.

### Findings JSON and `audited_languages`

`audited_languages` and `coverage` are load-bearing: populate both for every
language touched, clean or not. Shape: `references/audit-doc-output.md`.

### Output

Render with `scripts/build_audit_doc.py` (default `html,md`); the deliverable
never shows verdict tags or review attribution. Details: `references/audit-doc-output.md`.

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

The audit doc is the input to native review, never its output: it must not
attribute the agent's judgments to a native reviewer. When verdicts arrive, load
`references/post-review-triage.md` before capturing them with `scripts/apply_verdicts.py`.

---

## Phase 6 — Verify fixes

No `audited → verified` move until the deployment gate (deployed at all, then
when) is answered from evidence and a fresh re-fetch, never cached data, shows
the fix. Load `references/verify-fixes.md` when the client reports fixes deployed.

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

Use the scripts in `scripts/` rather than reimplementing their logic; never
hand-roll CSV moves. Load `references/bundled-scripts.md` when choosing a
script, before the first run in a project, or on a missing-module error.

---

## Pre-flight verification (before delivering an audit doc)

Before delivering an audit doc, the agent must re-read this skill's
rules, and the reference files this batch's episodes loaded, and check the doc against them. This is a quality gate, not
overhead — every rule violation that slips through erodes the audit's
credibility with the translators who act on it. Check in order:

1. **Flag, don't assert — and stay terse.** Every finding in **Likely
   errors** is one a non-native reviewer can defend without native
   fluency (register, idiom, anglicism go in **Worth checking**).
   Diagnoses name the anomaly only — no prescribed remedy ("should be
   X", and equally "typo for X" / "instead of X", which prescribe a
   correction in disguise), no asserted impact, nothing the excerpt
   already makes obvious. One root issue spanning several elements of
   the same page+language uses a shared `issue_group` instead of
   repeating the block.
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
   centrally over **all** of them and non-matches dropped — and the
   gate itself was negative-controlled (a known-bad excerpt injected
   into a scratch copy and confirmed caught).
6. **State is consistent.** After the audit, every URL in the batch
   has been moved from `open.csv` to `audited.csv`. No URL appears in
   two CSVs at once.
7. **Source pairing is correct.** Every non-source row's
   `canonical_url` was chosen by the priority order in Phase 2
   (`references/discovery-variants.md`; sitemap
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
   confirmed visibility — and no h1 visible-composition finding
   (duplicated text) is in Likely errors without a rendered check
   either. Any rendered h1 read confirmed the element itself was in
   layout (non-zero rect) before trusting `innerText`, applying the
   rendered-preferred / filtered-mobile-fallback logic on responsive
   sites, and the capture viewport is recorded in the cached data.
10. **No native-reviewer attribution in the deliverable.** The
    rendered `.html` / `.md` shows no "Confirmed by native review"
    tags, no "Dismissed by native review" subsections, no reviewer
    notes. Verdict state lives in the JSON only and feeds downstream
    artefacts.
11. **`audited_languages` is populated.** The findings JSON includes
    every language touched in the batch, so clean languages still
    surface a "No issues flagged in this batch." line in the
    deliverable.
12. **Coverage is shown, and not extrapolated.** The `coverage` map is
    populated for every audited language, so each section renders a
    "Pages checked" list — a clean language shows what was examined,
    not a bare "No issues". No statement in the doc generalises from
    the batch to unexamined URLs or from one translation to another;
    any sizing claim about a pattern rests on an enumerated sweep with
    per-locale counts (Phase 3).
13. **Grouped cards are coherent.** Every `issue_group` card's headline
    (`issue_title`, else the first diagnosis) is true of **all** its
    instances; a group bundles only same-theme findings, and mixed-type
    groups are split into separate cards — one card is one claim a
    reviewer can accept or reject as a unit.
14. **Claim verification ran over every assertive finding.** All
    Likely errors, plus Worth-checking findings naming a mechanical
    class, got the Stage-2 pass (`references/claim-verification.md`): buckets re-checked (mechanical
    classes promoted once visibility was confirmed, stale visibility
    hedges stripped), norm-invoking linguistic claims corroborated or
    reworded to the observable fact — with the impossible-morphology
    floor respected (a malformed inflection of a common word stays in
    Likely errors even uncorroborated) — and no remedies in disguise.
15. **Highlights are unambiguous.** Every `highlight` identifies its
    occurrence uniquely (word-boundary match, or disambiguating
    context included) — a mark on the wrong occurrence of a short
    token turns a correct finding into an apparent blunder.
16. **Phase 6 verdicts passed the deployment gate** (`references/verify-fixes.md`; shared rule —
    `redirect-verification/SKILL.md` § Shared verification rules, in the
    published open-source companion redirect-verification,
    https://github.com/rebelytics/redirect-verification). Where
    the batch carries verification verdicts, **whether** the fix was
    deployed at all is resolved — or the report says so in its opening
    line, offers no causal reading of the live state, and holds the
    `audited → verified` transitions; cache-busted live evidence does
    not exempt this. Every **Not fixed** verdict additionally rests on a
    deployment date sourced from evidence — never from a completion
    comment — and the fetch postdates it.

If any check fails, fix it before presenting the doc to the user.

---

## Quick reference

| Question | Answer |
|---|---|
| Where do new URLs go? | `urls/open.csv`, sorted by priority. |
| Where do findings go? | `findings/audit-YYYY-MM-DD-batch-N.html` (primary — tabs per language) + `.md` mirror; `.docx` only with `--format docx`. |
| When does a URL move from `open` to `audited`? | When the audit doc for its batch is written. |
| When does a URL move from `audited` to `verified`? | When the agent re-fetches it, confirms the fix is live, and the deployment gate (Phase 6, `references/verify-fixes.md`) is closed — a correct page alone does not establish that the reported fix shipped. |
| Can a URL move backward? | Yes — `audited` → `open` if a fix introduces a new issue. |
| What's the default batch size? | 20 for full audits (meta + body), 50 for meta-only. |
| Can a batch result be extrapolated to the rest of the site, or to other translations? | No — authored content has no generator to infer from, and translations of one document differ from each other. Coverage claims need enumeration; size a specific pattern with a targeted full sweep and per-locale counts (Phase 3). |
| What counts as a Likely error? | A pattern a non-native reviewer can defend without native fluency. |
| What counts as Worth checking? | A pattern that could plausibly be a deliberate translator choice. |
| When in doubt? | Worth checking, with a "could be deliberate" hedge. |
| How long should a diagnosis be? | As short as possible — name the anomaly only. No "should be X", no asserted impact, nothing the excerpt already shows. Many findings need none. |
| Same issue across a page's title/meta/H1? | Give them one `issue_group` → renders as a single card, not repeated blocks. (`issue_group` is within-language only.) |
| Same defect in several languages' equivalent field? | Emit it in **every** affected language tab — repetition across tabs is required, not just allowed. `issue_group` does not propagate across languages. |
| Auditing many locales at once? | One agent per language reading its cached JSON, then TWO mandatory central stages: the verbatim-excerpt gate (drop non-matches; state it in the agent contract; negative-control it), and the claim-verification pass over every assertive finding. Cover all page types, not just core pages. Load `references/scaling-across-locales.md` and `references/claim-verification.md` first. |
| Clear typo in the body, visibility now confirmed? | Promote to Likely error and strip the hedge — the hedge belonged to the visibility uncertainty, not the error class. |
| Diagnosis says "nonstandard per [language] orthography"? | That's an unverified norm-claim. Corroborate against the cached corpus (same word elsewhere on the site / in the source pair) or reword to the observable fact. |
| Morphologically impossible inflection of a common word, no in-page corroboration? | Assertable — an impossible form is not a usage claim. Keep in Likely errors. Corroborate-or-reword applies to convention claims, not malformed morphology. |
| H1 looks duplicated ("Artist Artist Album")? | Rendered check first — templates hide duplicate heading spans with CSS, and raw extraction concatenates them. Not a Likely error without rendered confirmation. |
| Rendered h1 capture still includes a hidden duplicate? | Check the element's rect — `innerText` falls back to `textContent` on unrendered elements (e.g. a mobile-only h1 at a desktop capture viewport). Prefer the first h1 with a non-zero rect; if none, filter the first h1's hidden descendants manually (skip the rect check on the root) and record the capture viewport. |
| Setting a `highlight`? | It must locate its occurrence unambiguously — add context if the token appears anywhere else in the excerpt (even mid-word). The renderer marks word-boundary matches only. |
| Grouped card with several distinct items? | Give the group an `issue_title` headline true of the whole block; group only same-theme findings and split mixed-type ones into separate cards. |
| What if direct HTTP fetch is blocked? | Cloudflare JS challenge or rate-limit (403/418/429) defeats `requests` even with full headers — use the browser-fetch playbook (`references/browser-fetch.md`): probe sibling-domain CORS first (open CORS = fetch every locale from ONE tab), accumulate in `window`, exfiltrate via the OPFS bridge (`collect_browser_dump.py`). Or `fetch_pages.py --from-csv` with a Screaming Frog / browser export. |
| Browser downloads / clipboard / localhost POST all fail silently? | Expected in automated browser sessions. Use the OPFS bridge (`references/browser-fetch.md`): write the payload with a marker prefix via `navigator.storage.getDirectory()`, collect from the profile's `File System/` store with `collect_browser_dump.py`. |
| Rendered verification long after the fetch? | Don't — verify close to fetch. On time-variant surfaces (carousels, campaign slots) a not-in-DOM verdict means "content rotated, unverifiable", not "false positive"; record removals in the project notes. |
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

---

## Feedback on this skill

If the user has methodology feedback, offer to draft a report for
https://github.com/rebelytics/translation-audit; before drafting, search that
repository's open and closed issues and pull requests for the same problem,
and read its CONTRIBUTING file for how the maintainer takes reports. If the
problem is the agent not following the skill's rules, acknowledge and correct
it instead.

Translation Audit: Eoghan Henn and contributors | CC BY 4.0
