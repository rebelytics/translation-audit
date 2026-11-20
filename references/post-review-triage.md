# Phase 5.5 — Post-review triage — translation-audit reference

Reference file for the `translation-audit` skill (CC BY 4.0 — Eoghan Henn
and contributors). Load it when native-reviewer verdicts arrive, before
capturing them, and before building a fix list. The sections below are moved
verbatim from the skill core with their headings unchanged. A section named
here (a phase, Principle 1, a heading) is a heading of `SKILL.md`; where
that section moved, its stub there names the file that now holds it.

Load triggers: native-reviewer verdicts arrive; building the fix list

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
