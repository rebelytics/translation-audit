# Audit doc — structure, findings JSON and output — translation-audit reference

Reference file for the `translation-audit` skill (CC BY 4.0 — Eoghan Henn
and contributors). Load it before writing the findings JSON and before
rendering the deliverable. The sections below are moved verbatim from the
skill core with their headings unchanged. A section named here (a phase,
Principle 1, a heading) is a heading of `SKILL.md`; where that section
moved, its stub there names the file that now holds it.

Load triggers: writing the findings JSON; rendering the deliverable with build_audit_doc.py

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
`highlight` (a substring of the excerpt to mark in the HTML — must
identify its occurrence unambiguously; `build_audit_doc.py` marks
word-boundary matches only and skips marking rather than mark the
wrong occurrence of an ambiguous token). The full per-finding shape
is documented at the top of `build_audit_doc.py`.

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

**Optional origin pass — group findings by who can fix them.** Where the
site's codebase is available, trace each finding to the code path or data
store that renders it. Record its fix route in an optional `fix_route`
field on the finding: `code` (a pull request), `cms` (an entry edited in
the admin), `translation-import` (the translation table or spreadsheet),
or `product-data`. The client team acts by owner, not by symptom, and one
symptom can have several routes: an English fallback can be a missing
translation row or a locale-mapping bug in code. `build_audit_doc.py`
does not render the field; use it for the fix list that follows native
review (Phase 5.5).

The deliverable **must not** show verdict tags or review attribution.
The audit doc is INPUT to native review, not OUTPUT of it (see
Phase 5.5 — Post-review triage).
