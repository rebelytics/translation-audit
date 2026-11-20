# Stage 2 — claim verification — translation-audit reference

Reference file for the `translation-audit` skill (CC BY 4.0 — Eoghan Henn
and contributors). Load it after the verbatim gate and the rendered pass,
before building any audit doc that carries assertive findings. The sections
below are moved verbatim from the skill core with their headings unchanged.
A section named here (a phase, Principle 1, a heading) is a heading of
`SKILL.md`; where that section moved, its stub there names the file that now
holds it.

Load triggers: before building an audit doc that carries assertive findings; a pre-flight claim-verification check fails

### Stage 2 — claim verification and re-bucketing (mandatory)

The verbatim gate proves the excerpts are real. It proves nothing
about the **claims made on top of them** — and wrong buckets,
unverifiable linguistic assertions and remedies-in-disguise are what
actually erode a reviewer's trust. After the verbatim gate (and after
the rendered visibility pass), run a second pass over every
**assertive finding**: all Likely errors, plus every Worth-checking
finding whose diagnosis names a mechanical error class (typo,
contamination, duplication, encoding). Per finding, answer:

1. **Is the bucket right for the class — especially after visibility
   cleared?** The raw-HTML rule forces body findings into Worth
   checking; once the rendered pass confirms visibility, findings of
   mechanical classes (typo, cross-language contamination, encoded
   entities, duplication) move **up** to Likely errors — and the
   hedge, which belonged to the *visibility* uncertainty and not the
   class, is stripped. Leaving "looks like a typo … worth a translator
   review" on a visibility-confirmed, unambiguous typo reads as
   linguistic timidity and buries real defects among judgment calls.
2. **Is every linguistic claim corroborated or reworded?** A diagnosis
   that invokes a norm ("nonstandard per X orthography", "doubled
   determiner") asserts something nobody checked — and attested
   idioms, legal boilerplate and regional conventions WILL contradict
   it. Corroborate cheaply (the cached corpus is right there: does the
   site itself spell it differently elsewhere? does the source pair?)
   or reword the diagnosis down to the observable fact ("spelling
   differs from the same word elsewhere on the page"), which survives
   native review even when the norm-claim wouldn't.

   **The skepticism has a floor — impossible morphology is
   assertable.** Corroborate-or-reword applies to claims about *usage
   and convention*. A morphologically impossible inflection of a
   common word — an impossible form, not an unusual choice — is
   defensible without in-page corroboration and stays in Likely
   errors. Worked contrast: a doubled determiner construction is
   unusual but could be attested legal boilerplate or idiom → defer
   to Worth checking unless corroborated; a malformed superlative of
   a common adjective (a form the language simply does not have, where
   only one well-formed superlative exists) has no attested reading
   at all → keep in Likely errors even when the page offers no
   corroborating counterpart. Over-applied skepticism relabels certain
   knowledge as doubt, which costs credibility the same way
   overclaiming does — just in the opposite direction.
3. **Is a remedy hiding in the diagnosis?** "Typo for X" / "instead of
   X" prescribe a correction just as much as "should be X" — and the
   implied correction can itself be wrong (a German plural that takes
   no -s). Quoting the source field is fine; naming the "intended"
   word is not. Add these patterns to the diagnosis post-scan.
4. **Is the group one claim?** A card that bundles several distinct
   micro-claims (a doubled word + an abbreviation redundancy + a brand
   casing) lets one disputed sub-claim taint the others. One card =
   one claim a reviewer can accept or reject as a unit.
5. **Is the highlight unambiguous?** See the highlight rule in
   Phase 5 — a short token that also occurs inside longer words gets
   marked in the wrong place by the renderer.

This stage exists because per-finding attention is exactly what the
fan-out trades away: isolated per-locale agents classify sloppily at
the margins, and a central review that only greps for rule phrases is
statistical, not per-claim. Scale the verification to the same surface
the reviewer reads — every assertive finding gets one adversarial pass
before delivery. Languages are independent here too, so this stage
fans out the same way the audit does.
