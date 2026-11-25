# Bundled scripts and dependencies — translation-audit reference

Reference file for the `translation-audit` skill (CC BY 4.0 — Eoghan Henn
and contributors). Load it when choosing a script, before the first script
run in a project, and on a missing-module error. The sections below are
moved verbatim from the skill core with their headings unchanged. A section
named here (a phase, Principle 1, a heading) is a heading of `SKILL.md`;
where that section moved, its stub there names the file that now holds it.

Load triggers: choosing a script; first script run in a project or a dependency error

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
  `visibility: hidden` containers before returning body text — and
  applies the same drops inside the `<h1>` subtree, since templates
  hide parts of headings with CSS. Tolerates bs4 ≥ 4.13's behaviour
  of surfacing already-decomposed elements in later attribute scans.
  Supports `--from-csv` mode to read pre-extracted content from a CSV
  instead of fetching, for use in sandboxed environments.
- **`collect_browser_dump.py`** (Phase 4, browser-fetch playbook) —
  the disk side of the OPFS bridge. After in-page JS writes the
  fetched-HTML payload (with a unique marker prefix) to the Origin
  Private File System, this script locates the newest matching file
  under the browser profile's `File System/` store, verifies the
  marker, and extracts the JSON payload to a target path. `--print-js`
  prints a template of the in-page collector for reference.
- **`build_audit_doc.py`** (Phase 5) — assembles the reviewer-facing
  deliverable from a findings JSON at `findings/raw/batch-NN.json`.
  Default output `html,md`: a self-contained **HTML report with one tab
  per language** (inline CSS/JS, no dependencies — the primary
  deliverable) plus a Markdown mirror; `--format docx` adds a Word file
  (needs python-docx). Renders a summary header, a "sample audit — not a
  complete crawl" scope banner, the Likely errors / Worth checking split,
  a **Pages checked** list per language (from the `coverage` map), and
  collapses findings that share an `issue_group` into one card headlined
  by `issue_title` (else the first finding's diagnosis); a group that
  spans pages gets its count in the headline, is capped by `group_caps`
  / `--max-instances`, and has every instance written to
  `…-instances.csv`. An optional `overview` block renders as a first
  Overview tab. Offline tests, run from the skill directory:
  `python3 -B -I scripts/tests/test_build_audit_doc.py`. Prefixes
  body-layer findings by `sub_type` (`[DOM-only, not rendered]` /
  `[Visibility unconfirmed …]`), HTML-escapes excerpts so literal markup
  shows verbatim, emits "No issues flagged in this batch." for every
  clean `audited_languages` entry, and prints a footer with author
  attribution + CC BY 4.0. Highlights are marked on **word-boundary
  occurrences only** — a single embedded match is honoured, multiple
  ambiguous matches get no mark rather than a wrong mark. The
  deliverable **does not** show verdict state — see Phase 5.5.
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
