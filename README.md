# Translation Audit

**A structured methodology for auditing translation quality on multilingual
websites at scale — without needing a native speaker of every language at
your desk.**

Part of the [Open Skill Library](https://github.com/rebelytics/one-skill-to-rule-them-all/blob/main/OPEN-SKILL-LIBRARY.md), the open-source agent skills maintained with Task Observer.

Translation quality on large multilingual sites tends to drift quietly.
Strings get re-translated by AI, content gets ported between platforms,
language teams shrink, and nobody is watching every version at once.
The result: meta descriptions in the wrong language, typos that survived
six redesigns, body copy that contradicts the source, and product pages
where a key noun has been translated as something unrelated.

Translation Audit systematises the review process so one person (or one
AI agent) can produce credible findings across an entire multilingual
site, then hand them to the people who actually fix things — native
speakers, the in-house translation team, or external linguists.

## What it does

A six-phase workflow the agent runs for you:

1. **Setup** — capture source / target languages, sitemap URL(s),
   batch size, and output preferences.
2. **Discover** — fetch the XML sitemap(s) and populate the audit
   queue. Falls back to on-page hreflang for sites with per-ccTLD
   layouts.
3. **Prioritise** — apply whatever data you have (GSC clicks, GA4
   sessions, page-type weights) to sort the queue by importance.
4. **Fetch** — capture live page content (title, H1, meta description,
   body text). Uses a rendered browser pass for the body layer when
   available.
5. **Audit** — flag findings against a structured error taxonomy and
   produce a deliverable (a self-contained HTML report with per-language
   tabs, plus a Markdown mirror) grouped by language, with a "Likely
   errors / Worth checking" split that lets non-native reviewers
   contribute credibly.
6. **Verify** — re-fetch URLs after fixes deploy and move them
   between state lists (`open → audited → verified`, or back to the
   queue if a fix introduced a new issue).

State lives in plain CSV files; the whole project is a folder of text
and CSV — readable, diff-friendly, portable across systems, and
re-runnable.

## What it deliberately does not do

- **Auto-translate or auto-fix.** The deliverable is an audit doc a
  human acts on.
- **Claim native-speaker authority.** Non-native reviewers (or the
  agent) flag rather than assert. Every finding is "Likely error"
  (defensible without native fluency) or "Worth checking" (deliberate
  translator choice possible).
- **Render verdict tags in the audit doc.** The doc is INPUT to
  native review, not output. Reviewer verdicts feed a separate fix
  list rather than the deliverable.

## Who it's for

SEO consultants and in-house teams who manage multilingual sites,
translation team leads who want structured input rather than "the
site looks weird, can you check it?", and anyone running a site
across more than three or four languages who needs a repeatable
review cadence.

You don't need to be a developer. If you can run a Python script,
you can run this skill end-to-end.

## Compatibility

**Designed for:** Claude Cowork, Claude Code, Claude.ai (with a
workspace-folder equivalent), and any Agent Skills-compatible
platform.

**Recommended (not required):** A rendering-capable browser
integration for your agent — e.g. Claude in Chrome — for the body
layer. The cheap-HTTP path is reliable for user-facing metadata
(title, meta description, H1) but over-captures hidden DOM content
as body text. See USER-GUIDE.md for setup and fallback.

**Requirements:** Python 3.9+, `requests`, `beautifulsoup4`, `PyYAML`.
`python-docx` is optional — only for the Word (`.docx`) export; the
default HTML + Markdown deliverables need no third-party packages. See
`requirements.txt`.

## Companion skill

The verification phase applies shared rules — the deployment gate and the
emitter classification that decides whether a sample is valid — owned by
the published companion skill
[redirect-verification](https://github.com/rebelytics/redirect-verification).
Install it alongside translation-audit; this skill points to it rather than
carrying its own copy.

## Quick start

1. Clone this repo into your workspace folder (or wherever your agent
   reads skills from).
2. `pip install -r requirements.txt`
3. Open a session and ask the agent to set up a new translation
   audit project.

See [USER-GUIDE.md](USER-GUIDE.md) for the short walkthrough.

## Repo layout

```
translation-audit/
├── SKILL.md                    # the skill definition (for the agent)
├── README.md                   # this file
├── USER-GUIDE.md               # short walkthrough
├── LICENSE                     # CC BY 4.0
├── requirements.txt
├── scripts/
│   ├── fetch_sitemap.py        # sitemap → open.csv (hreflang-aware)
│   ├── build_mapping.py        # fallback for per-ccTLD sites
│   ├── fetch_pages.py          # URL batch → cached page content
│   ├── collect_browser_dump.py # OPFS browser→disk bridge (bot-blocked sites)
│   ├── build_audit_doc.py      # findings JSON → .html + .md (+ docx opt-in)
│   ├── apply_verdicts.py       # post-review verdict CSV → JSON
│   ├── state.py                # three-list lifecycle bookkeeping
│   └── tests/                  # offline tests for build_audit_doc.py, with a fixture
├── references/
│   ├── ceilings.txt            # declared line ceilings per file
│   ├── discovery-variants.md   # Phase 2: source-language regional variants
│   ├── browser-fetch.md        # Phase 4: browser-fetch playbook for bot-blocked sites
│   ├── rendered-verification.md # Phase 4: the rendered browser pass
│   ├── scaling-across-locales.md # Phase 5: fanning the audit out per language
│   ├── claim-verification.md   # Phase 5 Stage 2: verifying assertive findings
│   ├── audit-doc-output.md     # Phase 5: section structure, findings JSON, output
│   ├── post-review-triage.md   # Phase 5.5: native-reviewer verdicts
│   ├── verify-fixes.md         # Phase 6: verifying deployed fixes
│   ├── bundled-scripts.md      # choosing and running the bundled scripts
│   └── error-taxonomy.md       # full taxonomy with worked examples
└── assets/
    ├── config.yml.template
    ├── open.csv.template       # state-CSV templates (also
    ├── audited.csv.template    # audited / verified / excluded)
    ├── verified.csv.template
    ├── excluded.csv.template
    └── findings.json.template  # finding-record schema
```

## Contributing

Early release. Bug reports, feature requests, new error-class
examples, and platform compatibility reports all welcome via Issues
and PRs.

## Credits

- Original author: [Eoghan Henn](https://www.rebelytics.com) / [LinkedIn](https://www.linkedin.com/in/eoghanhenn)

## License

CC BY 4.0 — the licence text is in [LICENSE](./LICENSE): the full legal code, unmodified, as Creative Commons publishes it; the [human-readable summary](https://creativecommons.org/licenses/by/4.0/) says what it allows. Use it, fork it, adapt it, monetise it. Keep the attribution.

Copyright (c) 2026 Eoghan Henn / rebelytics.com
