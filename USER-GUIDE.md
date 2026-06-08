# Translation Audit — user guide

A short walkthrough. The skill (`SKILL.md`) is detailed; this guide just
shows what to ask the agent for and what to expect back.

---

## Before you start

- A workspace folder your agent reads/writes (Cowork: the folder you
  select at session start; Claude Code: the project root).
- The `translation-audit` skill installed.
- Python 3.9+ and `pip install -r requirements.txt`.
- The XML sitemap URL for the site you want to audit.

That's it.

### Recommended: enable a rendering-capable browser integration

The audit's body layer is significantly more accurate when the agent
can extract **visible rendered text** rather than raw HTML. Without a
rendered fetch, hidden templates (`<template>`, `[hidden]`,
`display:none` containers) and JS notification strings show up in the
audit as if they were visible body text — and the audit will sometimes
flag English strings that don't actually appear on the page as
"untranslated content".

The fix is to enable a browser integration that exposes only rendered
visible text. The agent will use it automatically if it's available.

**By environment:**

- **Claude Cowork (desktop app):** install the Claude in Chrome
  extension (Chrome or Edge), make sure the browser is running, and
  open the Cowork chat. The integration is available once both
  conditions are met.
- **Claude Code (desktop app, VS Code, JetBrains):** install the
  Claude in Chrome extension; the integration is available once the
  extension is installed and the host browser is running.
- **Claude Code (terminal):** opt in explicitly — either launch with
  `claude --chrome`, or run `/chrome` inside an active session. You
  can also set it to be enabled by default in your Claude Code
  config.
- **Other Agent Skills-compatible platforms:** check whether the
  platform exposes a "rendered page text" tool to skills (the
  equivalent of `get_page_text` in the Claude tooling). If yes,
  enable it. If no, the audit runs on the raw-HTTP fallback.
- **Not available on:** WSL, third-party model providers (Bedrock,
  Vertex, Foundry), non-Chromium browsers. These environments are
  limited to the raw-HTTP fallback.

**Requirements for Claude in Chrome:** Chrome or Edge with the
extension installed, a direct paid Anthropic plan (not via a
third-party cloud provider).

**If the integration isn't available:** the audit still works.
`fetch_pages.py` runs with `requests` + BeautifulSoup, captures
metadata reliably, and skips the most obvious hidden containers in
the body. Body findings then carry a `[Visibility unconfirmed]`
prefix and the native reviewer verifies them on the live page.

---

## The conversation

A whole project from setup to verification is six short prompts.

```
> Set up a translation audit for example.com. Source English,
  targets German, French, Spanish. Sitemap is at
  https://example.com/sitemap.xml.

> Run discovery.

> Prioritise. My GSC clicks export is in prioritisation/inputs/.

> Audit the next batch.

> Apply the verdict CSV at native-verdicts-batch-01.csv to batch 01.

> The German fixes from batch 01 have been deployed. Verify them.
```

The agent handles the work. Each phase is described in detail in
SKILL.md — you don't need to remember any of it.

### What lands where

- `urls/open.csv / audited.csv / verified.csv / excluded.csv` — the
  state lists; `state.py` moves URLs between them.
- `data/pages-{lang}-batch-N.json` — cached live page content.
- `findings/raw/batch-NN.json` — raw findings (the canonical data store).
- `findings/audit-YYYY-MM-DD-batch-NN.docx` + `.md` — the reviewer-facing
  deliverable you send to your translator or in-house language lead.
- `prioritisation/inputs/` — drop your GSC / GA4 / page-type weight
  files here; the agent reads them.
- `prioritisation/notes.md` — rationale of how the priority score was
  built.

### Per-language handoff

The audit doc is grouped by language and each section is
self-contained. You can paste a single language section into an email
to the responsible reviewer without losing context. The "Likely
errors" / "Worth checking" split tells them where to act with
confidence and where to make a judgment call.

The doc deliberately does **not** show any "Confirmed / Dismissed by
native review" tags — it's INPUT to native review, not output. The
reviewer's verdicts come back via the CSV in the next step.

### Capturing the native reviewer's verdicts

The reviewer fills out a small CSV with columns `url, field, excerpt,
review_status, review_note`. `review_status` is one of `confirmed` /
`dismissed` / `edited`. Drop it in the project folder and ask the
agent to apply it (third prompt above) — `apply_verdicts.py` merges
the verdicts into the findings JSON.

The set of `confirmed` findings is the fix list. Phase 6
verification checks those URLs against the live site.

---

## Common variations

**Multiple projects in one workspace.** Use different project names:
"Set up an audit called acme-audit." The agent creates a sibling
folder.

**Re-audit verified URLs to catch regressions.** "Re-audit 50 random
URLs from verified.csv." The agent uses `state.py reaudit` to move
them back to `open.csv` with a note.

**Exclude irrelevant URLs.** "Exclude all URLs under /redirect/.
Reason: server redirects." The agent uses `state.py exclude` to move
them with the reason attached.

**No direct HTTP access.** "Audit the next batch from the Screaming
Frog export at sf-export.csv." The agent calls `fetch_pages.py
--from-csv`.

**Per-domain ccTLD sites without sitemap hreflang.** Common on
PrestaShop / Magento. "The sitemaps have no hreflang. Use
build_mapping.py with this source sitemap: ..." The agent walks the
source pages and reads on-page hreflang to build the mapping.

**Resuming a project later.** "Load the example-com-audit project."
State lives in the four CSV files; no session memory needed. Pause
for weeks, switch agents, pick up where you left off.

---

## Troubleshooting

**Sitemap fetch returned 0 URLs.**
Either the sitemap URL is wrong (check `[domain]/robots.txt` for the
real location), or the site keeps each language on its own ccTLD
without sitemap hreflang — use `build_mapping.py` instead.

**Page fetches return non-200 status codes.**
Common causes: Cloudflare bot protection, geo-blocking, or redirects
to a different domain. Inspect `status` and `final_url` in
`data/pages-*.json`. URLs that redirect to a non-localised target
probably belong in `excluded.csv`.

**Audit flagged English strings that don't visibly appear on the page.**
The body layer is being extracted from raw HTML without a rendered
fetch — the strings live in JS notification templates, hidden cart
strings, or `<template>` elements. Fix: enable a browser integration
(see "Before you start"), or have the reviewer dismiss the affected
`visibility_unconfirmed` findings.

**Too many "Worth checking" flags on the first batch.**
Expected. The taxonomy is intentionally generous — better to
over-flag than under-flag. Once the reviewer gives feedback on the
first batch, you'll know which classes to tighten for this site.

---

## Licence

CC BY 4.0. Created by [Eoghan Henn](https://rebelytics.com).
