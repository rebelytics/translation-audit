# Phase 6 — Verify fixes — translation-audit reference

Reference file for the `translation-audit` skill (CC BY 4.0 — Eoghan Henn
and contributors). Load it when the client reports fixes deployed, before
the first re-fetch. The sections below are moved verbatim from the skill
core with their headings unchanged. A section named here (a phase, Principle
1, a heading) is a heading of `SKILL.md`; where that section moved, its stub
there names the file that now holds it.

Load triggers: the client reports fixes deployed; the pre-flight deployment-gate check on Phase 6 verdicts

When the client confirms that fixes for an audit batch have been
deployed, the agent verifies them and moves URLs from `audited.csv` to
`verified.csv`.

**The deployment gate — whether it shipped, then when.** Shared rule —
see `redirect-verification/SKILL.md` § Shared verification rules
(deployment gate), in the published open-source companion
redirect-verification (https://github.com/rebelytics/redirect-verification):
two ordered questions precede every verdict — was the
fix deployed at all, then when. The client's confirmation usually
arrives as a ticket comment or an email, which dates the report, not the
change. The instance here:

- While Question 1 (deployed at all?) is unresolved, say so in the
  report's opening line, report live state plainly with no causal
  reading of it, and hold the `audited → verified` transitions.
- A **Verified** verdict that attributes the change to the reported fix
  needs Question 1 — the page may have been correct all along or fixed
  by something unrelated, and a cache-busted re-fetch does not exempt
  it.
- A **Not fixed** verdict additionally needs Question 2: the re-fetch
  must postdate a deployment date pinned from evidence. If the date
  cannot be pinned, record the range in `prioritisation/notes.md`,
  treat "Not fixed" as provisional, and re-check once the date is
  established rather than incrementing `verify_attempts` against a fix
  that had not yet shipped.

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
