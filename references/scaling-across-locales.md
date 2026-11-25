# Scaling the audit across locales — translation-audit reference

Reference file for the `translation-audit` skill (CC BY 4.0 — Eoghan Henn
and contributors). Load it before dispatching per-language agents and before
building a cross-market overview. The sections below are moved verbatim from
the skill core with their headings unchanged. A section named here (a phase,
Principle 1, a heading) is a heading of `SKILL.md`; where that section
moved, its stub there names the file that now holds it.

Load triggers: dispatching per-language agents; building a cross-market overview

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

Two practices keep the gate honest:

- **State the gate in the agent contract.** Tell each agent its
  excerpts will be literal-substring-checked against the cached JSON
  and that non-matches are dropped. Agents that know the check exists
  copy-paste rather than paraphrase — in practice this turns the gate
  from a filter into a deterrent (a 25-agent run produced 470/470
  verbatim excerpts under this contract).
- **Negative-control the gate.** A gate that has never been seen to
  fail is indistinguishable from a gate that never ran. Before
  trusting a 100% pass, inject one corrupted excerpt and one corrupted
  `source_excerpt` into a **copy** of the results and confirm both are
  caught — and make the control non-destructive (point it at a scratch
  output path; a control run that overwrites the real findings JSON
  has to be re-run with the real input afterwards).

**For an overview across many locales, detect first, then read.** Where
the goal is a cross-market overview rather than an exhaustive per-page
audit, one agent per language is the expensive route and the less
consistent one. The cheaper route has three stages:

1. **Automated candidate pass over the cached pages:** per-block
   stopword language identification; an identical-to-source check that
   **excludes strings present on 60% or more of locales** (artist,
   product or release names, which are legitimately identical); mentions
   of another market's domain; entity or markup leaks; missing metas.
   Run the identical-to-source check only where the source block itself
   classifies as the source language. A market-specific page can exist on
   the source domain in the market's own language — a country's warranty
   terms, say — and then a correct translation matches its "source".
   Call a block the source language only on two or more distinct
   source-language stopwords, or above a minimum block length set for the
   project. A short title shares a single stopword with the source
   language by chance: "Sofás a medida" is Spanish, not English.
2. **A manual read of the title / meta / H1 layer per market**, printed
   side by side, which is where most visible defects sit and which a
   detector reads worst.
3. **Findings built by a script that cuts every excerpt from the cache**,
   so the verbatim gate passes by construction — and is still run and
   negative-controlled, because a gate never seen to fail proves nothing.

Two detector artefacts would otherwise become false Likely errors: block
segmentation by an element's direct text children splits a sentence at
an inline link (the fragment "Der Widerruf kann mit unserem erfolgen" was
complete in `body_text`), so confirm a truncated-sentence candidate
against `body_text`; and byte-based truncation in the inspection pipeline
produces U+FFFD that is not in the raw HTML, so confirm any broken
character on the raw bytes. A pattern repeating across many pages of one
language (an English meta layer, a reused homepage meta, legal pages
naming another market's domain) is reported once with its count in the
headline and every instance in an accompanying file — listing each
instance buried the findings in one run (774 cards, 418 after capping).
`build_audit_doc.py` does both from one `issue_group` spanning the pages
(`group_caps` / `--max-instances`); the cross-market layer goes in the
findings' optional `overview` block.
