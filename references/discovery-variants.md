# Discovery — source pairing and regional variants — translation-audit reference

Reference file for the `translation-audit` skill (CC BY 4.0 — Eoghan Henn
and contributors). Load it before Phase 2 writes `urls/open.csv` or
`data/url-mapping.json`, and whenever a comparison source URL or a regional
target variant is chosen. The sections below are moved verbatim from the
skill core with their headings unchanged. A section named here (a phase,
Principle 1, a heading) is a heading of `SKILL.md`; where that section
moved, its stub there names the file that now holds it.

Load triggers: Phase 2 discovery, before open.csv or url-mapping.json is written; choosing a comparison source URL or a regional target variant

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
