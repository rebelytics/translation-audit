# Browser-fetch playbook — translation-audit reference

Reference file for the `translation-audit` skill (CC BY 4.0 — Eoghan Henn
and contributors). Load it when scripted HTTP is bot-blocked and a browser
integration is available, before the first navigation. The sections below
are moved verbatim from the skill core with their headings unchanged. A
section named here (a phase, Principle 1, a heading) is a heading of
`SKILL.md`; where that section moved, its stub there names the file that now
holds it.

Load triggers: scripted HTTP bot-blocked with a browser integration available; browser downloads, clipboard or localhost POST failing silently

### Browser-fetch playbook for bot-blocked multi-domain sites

When the site bot-blocks scripted HTTP (403/429/418 even with full
browser headers) and the agent has a browser integration, the
efficient shape is NOT one navigation per page. In order:

1. **Probe cross-domain CORS first.** Sibling ccTLD domains run by one
   company often serve permissive CORS to each other. One probe
   (`fetch('https://sibling-domain/page')` from any one of them) can
   collapse the whole plan: if readable, fetch **every** locale's pages
   from a single tab with plain `fetch()` — no per-domain navigation
   at all. A 10-second probe can replace dozens of navigations.
2. **Accumulate in the page, not the conversation.** Store fetched
   HTML in a `window` variable across calls; return only status codes.
   Raw HTML for a full batch (tens of MB) must never flow through the
   agent conversation.
3. **Get the data to disk via OPFS.** In automated browser sessions,
   the user-mediated escape hatches are routinely blocked without any
   visible error: blob downloads are silently suppressed (even with a
   real-gesture click), `navigator.clipboard` throws (document not
   focused), and localhost POSTs hang on a Local Network Access
   permission no automation can answer. The channel that needs no
   permission is the **Origin Private File System** — write the
   payload with a unique marker prefix via
   `navigator.storage.getDirectory()`, then locate and extract it from
   the browser profile directory on disk (Chrome stores OPFS content
   as plain files under `<profile>/File System/`). The bundled
   `scripts/collect_browser_dump.py` does the locate-verify-extract
   step. Test any transfer channel with a tiny payload before
   committing the real one.
4. **Fall back to per-domain same-origin fetch** only when the CORS
   probe fails: navigate to each domain once, `fetch()` its paths
   same-origin, and exfiltrate via the same OPFS bridge.

Then run the standard extraction (`fetch_pages.extract_fields`) over
the dumped HTML and write `data/pages-{lang}-batch-N.json` in the
normal schema — everything downstream of Phase 4 is unchanged.
