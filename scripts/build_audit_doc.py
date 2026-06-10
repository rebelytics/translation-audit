#!/usr/bin/env python3
"""
build_audit_doc.py — assemble the audit deliverable from a findings JSON.

The audit doc is a **reviewer-facing artefact**: it presents findings
TO a native speaker so they can decide which to fix. It must not
attribute any verdict to a native reviewer who has not seen the
document yet. Verdict state (review_status / review_note / reviewer)
is captured AFTER native review via apply_verdicts.py and lives in
the findings JSON, but is deliberately not rendered in this
deliverable; it feeds downstream artefacts (e.g. a fix list) that are
out of scope for this script.

Primary output is a self-contained **HTML report with per-language
tabs** (zero dependencies — inline CSS/JS, opens in any browser, and
prints cleanly to PDF for a client hand-off). A Markdown mirror is
written for version control. A .docx is available behind `--format
docx` for clients who require Word, but it is no longer a default.

Findings JSON shape:

  {
    "project_name": "example-com-audit",
    "audit_date": "2026-05-28",
    "batch_number": 1,
    "source_language": "en",
    "audited_languages": ["de", "fr", "es"],   # optional but recommended
    "coverage": {                              # optional: per-language audited
      "de": ["https://example.com/de/a", ...], # URLs — renders the "Pages
      "fr": ["https://example.com/fr/a", ...]  # checked" list per language
    },
    "findings": [
      {
        "language": "de",
        "url": "https://example.com/de/produkt",
        "field": "meta_description",          # or "title" / "h1" / "body"
        "excerpt": "...",                     # exact text from the page
        "diagnosis": "...",                   # TERSE: name the anomaly only
        "bucket": "likely_error",             # or "worth_checking"
        "source_excerpt": null,               # or the source-language equivalent
        "sub_type": null,                     # "dom_only_not_rendered"
                                              # or "visibility_unconfirmed"
        "issue_group": null,                  # optional: findings that share
                                              # this key (within one language)
                                              # render as ONE card with several
                                              # instances, instead of repeating
                                              # the same diagnosis per element
        "issue_title": null,                  # optional: group-level headline
                                              # for the card — set this when a
                                              # group bundles several findings so
                                              # the headline fits the WHOLE block
        "highlight": null,                    # optional: substring of excerpt
                                              # to <mark> in the HTML
        "review_status": "unreviewed",        # captured post-review only
        "review_note": null,                  # captured post-review only
        "reviewer": null                      # "native_speaker" once reviewed
      },
      ...
    ]
  }

Diagnosis style (enforced by the skill, not the script): name the
anomaly only. No prescribed remedy ("should be X"), no asserted
consequence ("breaks Y" / "shows as Z"), and nothing the excerpt
already makes obvious (e.g. that an English string on a localised page
is untranslated). Most findings need a few words or none at all.

Grouping: within a single language section, findings that share an
`issue_group` are rendered as one card — the diagnosis is stated once
and each affected element (field + URL + excerpt) is listed beneath
it. This removes the across-element repetition. Repetition ACROSS
languages is intentional: each language tab is self-contained so it
can be handed to that market's reviewer on its own.

Body sub-types prefix the diagnosis:
  - "dom_only_not_rendered"   → "[DOM-only, not rendered]"
  - "visibility_unconfirmed"  → "[Visibility unconfirmed — verify on rendered page]"

A language listed in `audited_languages` but with zero findings still
gets a tab that reads "No issues flagged in this batch." — coverage
(what was checked) and findings (what was wrong) are reported
independently.

Output:
  findings/audit-YYYY-MM-DD-batch-NN.html   (primary)
  findings/audit-YYYY-MM-DD-batch-NN.md     (mirror)
  findings/audit-YYYY-MM-DD-batch-NN.docx   (only with --format docx)

Usage:
  python build_audit_doc.py --findings findings/raw/batch-01.json \\
      --project-dir ./my-audit
"""

import argparse
import html
import json
import sys
from collections import defaultdict
from pathlib import Path

LANGUAGE_NAMES = {
    "ca": "Catalan",
    "cs": "Czech", "cz": "Czech",
    "da": "Danish", "dk": "Danish",
    "de": "German",
    "el": "Greek", "gr": "Greek",
    "en": "English",
    "es": "Spanish",
    "fi": "Finnish",
    "fr": "French",
    "hr": "Croatian",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "nl": "Dutch", "be": "Dutch (Belgium)",
    "no": "Norwegian", "nb": "Norwegian", "nn": "Norwegian (Nynorsk)",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sr": "Serbian",
    "sv": "Swedish", "se": "Swedish",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "vi": "Vietnamese",
    "zh": "Chinese", "cn": "Chinese",
}

FIELD_LABELS = {
    "title": "Title",
    "meta_description": "Meta description",
    "h1": "H1",
    "body": "Body",
}

BUCKETS = ["likely_error", "worth_checking"]
BUCKET_LABELS = {
    "likely_error": "Likely errors",
    "worth_checking": "Worth checking",
}

# Sub-type prefixes for body-layer findings.
SUB_TYPE_PREFIXES = {
    "dom_only_not_rendered": "[DOM-only, not rendered]",
    "visibility_unconfirmed": "[Visibility unconfirmed — verify on rendered page]",
}


def language_label(code: str) -> str:
    name = LANGUAGE_NAMES.get(code.lower(), code.upper())
    return f"{name} ({code})"


def normalise_bucket(value: str) -> str:
    return value if value in BUCKETS else "worth_checking"


def diagnosis_with_prefix(finding: dict) -> str:
    """Diagnosis text, optionally prefixed by a body-layer sub-type tag."""
    diagnosis = (finding.get("diagnosis") or "").strip()
    sub_type = (finding.get("sub_type") or "").strip()
    prefix = SUB_TYPE_PREFIXES.get(sub_type)
    if prefix:
        return f"{prefix} {diagnosis}".strip()
    return diagnosis


def group_findings(findings: list):
    """Group by language → bucket → list of findings (discovery order)."""
    grouped = defaultdict(lambda: defaultdict(list))
    lang_order = []
    for f in findings:
        lang = f.get("language", "unknown")
        bucket = normalise_bucket(f.get("bucket", "worth_checking"))
        if lang not in grouped:
            lang_order.append(lang)
        grouped[lang][bucket].append(f)
    return grouped, lang_order


def group_issues(items: list):
    """Collapse findings that share an `issue_group` into one issue with
    several instances. Findings without an issue_group stay solo. Order
    is preserved by first appearance. Each issue dict carries:
      diagnosis      — card headline: the group's `issue_title` if any finding
                       sets one (so it describes the whole block), else the
                       first finding's diagnosis
      shared_source  — the source_excerpt if identical across instances,
                       else None (then each instance shows its own)
      instances      — the original finding dicts
    """
    order, groups = [], {}
    for i, f in enumerate(items):
        key = f.get("issue_group") or f"__solo_{i}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(f)
    issues = []
    for key in order:
        fs = groups[key]
        srcs = {(g.get("source_excerpt") or "").strip() for g in fs}
        shared = srcs.pop() if len(srcs) == 1 else ""
        # Card headline: prefer an explicit group-level `issue_title` so a grouped
        # card describes the WHOLE block (not just the first item); fall back to the
        # first finding's diagnosis for solo findings / ungrouped use.
        title = next((g.get("issue_title") for g in fs
                      if (g.get("issue_title") or "").strip()), None)
        if title:
            sub = (fs[0].get("sub_type") or "").strip()
            prefix = SUB_TYPE_PREFIXES.get(sub)
            headline = f"{prefix} {title}".strip() if prefix else title.strip()
        else:
            headline = diagnosis_with_prefix(fs[0])
        issues.append({
            "diagnosis": headline,
            "shared_source": shared or None,
            "instances": fs,
        })
    return issues


def coverage_order(payload: dict, lang_order: list) -> list:
    audited = [c for c in (payload.get("audited_languages") or [])
               if c not in lang_order]
    return list(lang_order) + audited


def bucket_counts(grouped, lang):
    return {b: len(grouped[lang].get(b, [])) for b in BUCKETS}


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------

def _md_code(text: str) -> str:
    """Wrap an excerpt as an inline code span so literal markup (e.g. a
    stray <br>) shows verbatim instead of rendering."""
    text = (text or "").strip()
    if "`" in text:
        return '"' + text.replace("\n", " ") + '"'
    return "`" + text.replace("\n", " ") + "`"


def build_markdown(payload: dict) -> str:
    out = []
    project = payload.get("project_name", "Translation audit")
    audit_date = payload.get("audit_date", "")
    batch = payload.get("batch_number", "")
    source_lang = payload.get("source_language", "source")
    out.append(f"# {project} — translation audit, batch {batch:02d}" if isinstance(batch, int)
               else f"# {project} — translation audit")
    out.append("")
    out.append(f"**Audit date:** {audit_date}")
    out.append("")
    out.append(
        "Each section is one language version and is self-contained, so it can be handed "
        "to the native speaker for that market on its own. Items are grouped as **Likely "
        "errors** (patterns a non-native reviewer can flag confidently) and **Worth "
        "checking** (could be deliberate translator choices — flagged, not asserted). "
        "Findings name the anomaly only; the native speaker decides the fix."
    )
    out.append("")

    grouped, lang_order = group_findings(payload.get("findings", []))
    languages = coverage_order(payload, lang_order)
    if not languages:
        out.append("_No languages audited in this batch._")
        return "\n".join(out) + "\n"

    coverage = payload.get("coverage", {}) or {}
    findings_urls = {}
    for f in payload.get("findings", []):
        findings_urls.setdefault(f.get("language"), set()).add(f.get("url"))
    if coverage:
        cov_total = sum(len(v) for v in coverage.values())
        per_lang = cov_total // len(coverage)
        out.append(f"**Sample audit — not a complete crawl.** {cov_total} URLs checked "
                   f"({per_lang} per language across {len(coverage)} language versions), one page per "
                   f"page type. One batch in an ongoing series; a page with no finding was checked and "
                   f"came back clean.")
        out.append("")

    for lang in languages:
        out.append(f"## {language_label(lang)}")
        out.append("")
        cov = coverage.get(lang, [])
        if cov:
            fset = findings_urls.get(lang, set())
            out.append(f"**Pages checked ({len(cov)}):**")
            for u in cov:
                mark = "" if u in fset else " — _no issues flagged_"
                out.append(f"- {u}{mark}")
            out.append("")
        if lang not in grouped or not any(grouped[lang].get(b) for b in BUCKETS):
            out.append("_No issues flagged in this batch._")
            out.append("")
            continue
        for bucket in BUCKETS:
            items = grouped[lang].get(bucket, [])
            if not items:
                continue
            out.append(f"### {BUCKET_LABELS[bucket]}")
            out.append("")
            for issue in group_issues(items):
                diag = issue["diagnosis"]
                if diag:
                    out.append(f"- {diag}")
                else:
                    out.append("- _(see excerpt)_")
                if issue["shared_source"]:
                    out.append(f"  Source ({source_lang}): {_md_code(issue['shared_source'])}")
                for inst in issue["instances"]:
                    field = FIELD_LABELS.get(inst.get("field", ""), inst.get("field", ""))
                    url = inst.get("url", "")
                    out.append(f"  - **{field}** — {url}")
                    out.append(f"    {_md_code(inst.get('excerpt'))}")
                    isrc = (inst.get("source_excerpt") or "").strip()
                    if isrc and not issue["shared_source"]:
                        out.append(f"    Source ({source_lang}): {_md_code(isrc)}")
                out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# HTML (primary deliverable)
# --------------------------------------------------------------------------

HTML_CSS = r"""
:root{
  --ink:#1f2933; --muted:#6b7785; --line:#e3e8ee; --bg:#f4f6f9; --card:#fff;
  --likely:#c0392b; --likely-bg:#fdecea; --worth:#b8772b; --worth-bg:#fdf3e6;
  --accent:#2b7a78; --link:#1f5fbf;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;}
.wrap{max-width:1000px;margin:0 auto;padding:0 20px 64px;}
header.report{background:linear-gradient(135deg,#1f2933,#2b3a47);color:#fff;
  padding:34px 0 30px;margin-bottom:0;}
header.report .wrap{padding-bottom:0}
.report h1{margin:0 0 4px;font-size:26px;letter-spacing:-.01em;}
.report .sub{color:#b9c4cf;font-size:14px;margin-bottom:2px}
.report .src{color:#dce3ea;font-size:14px;margin-top:6px}
.report .src b{color:#fff;font-weight:600}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin:20px 0 4px}
.chip{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);
  border-radius:10px;padding:10px 14px;min-width:96px}
.chip .n{font-size:22px;font-weight:700;display:block;line-height:1.1}
.chip .l{font-size:12px;color:#c4ced8;text-transform:uppercase;letter-spacing:.04em}
.chip.likely .n{color:#ff8a7a}
.chip.worth .n{color:#ffc880}
.intro{color:#4a5560;font-size:13.5px;background:#fff;border:1px solid var(--line);
  border-radius:10px;padding:12px 16px;margin:20px 0 0}
.intro b.le{color:var(--likely)} .intro b.wc{color:var(--worth)}
.scope{color:#7a5d00;font-size:13px;background:#fffbef;border:1px solid #f0e2b8;border-radius:10px;padding:11px 15px;margin:12px 0 0}
.scope strong{color:#5e4700}
.coverage{margin:2px 0 16px;font-size:13px}
.coverage summary{cursor:pointer;color:var(--muted);font-weight:600}
.coverage ul{margin:8px 0 0;padding-left:18px}
.coverage li{margin:2px 0;word-break:break-all}
.coverage .ok{color:#2e7d46;font-size:12px}
nav.tabs{position:sticky;top:0;z-index:5;background:var(--bg);
  border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;gap:4px;
  padding:10px 0;margin:0 0 22px}
.tab{appearance:none;border:1px solid var(--line);background:#fff;color:var(--ink);
  border-radius:999px;padding:7px 14px;font-size:14px;cursor:pointer;
  display:inline-flex;align-items:center;gap:8px;transition:all .12s}
.tab:hover{border-color:#c2ccd6}
.tab.active{background:var(--ink);color:#fff;border-color:var(--ink)}
.tab .badge{font-size:12px;font-weight:700;background:#eef1f5;color:#48535f;
  border-radius:999px;padding:1px 8px;min-width:20px;text-align:center}
.tab.active .badge{background:rgba(255,255,255,.22);color:#fff}
.tab .badge.zero{background:#e6f4ea;color:#2e7d46}
.panel{display:none}
.panel.active{display:block;animation:fade .18s ease}
@keyframes fade{from{opacity:.3}to{opacity:1}}
.panel h2{font-size:20px;margin:4px 0 2px}
.panel .langmeta{color:var(--muted);font-size:13.5px;margin-bottom:18px}
.bucket{margin:0 0 26px}
.bucket h3{font-size:13px;text-transform:uppercase;letter-spacing:.05em;
  margin:0 0 12px;display:flex;align-items:center;gap:8px}
.bucket.likely h3{color:var(--likely)} .bucket.worth h3{color:var(--worth)}
.bucket h3 .count{background:#eef1f5;color:#48535f;border-radius:999px;
  font-size:12px;padding:1px 9px;letter-spacing:0}
.finding{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:16px 18px;margin:0 0 14px;border-left:4px solid var(--line)}
.finding.likely{border-left-color:var(--likely)}
.finding.worth{border-left-color:var(--worth)}
.finding .diag{font-size:15px;margin:0 0 12px;color:#27313b}
.finding .diag .tag{display:inline-block;font-size:11px;font-weight:700;
  text-transform:uppercase;letter-spacing:.03em;color:#8a5a00;background:#fbf0db;
  border-radius:5px;padding:1px 6px;margin-right:6px;vertical-align:middle}
.inst{padding:10px 0 0;border-top:1px dashed var(--line);margin-top:10px}
.inst:first-of-type{border-top:0;margin-top:0;padding-top:0}
.inst .head{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:6px}
.field{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;
  background:#eef1f5;color:#48535f;border-radius:5px;padding:2px 8px}
.url{font-size:13px;color:var(--link);text-decoration:none;word-break:break-all}
.url:hover{text-decoration:underline}
.excerpt{font:13.5px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  background:#f7f9fb;border:1px solid var(--line);border-radius:8px;
  padding:9px 12px;white-space:pre-wrap;word-break:break-word;color:#2b3640}
.excerpt mark{background:#ffe9a8;color:inherit;padding:0 2px;border-radius:3px}
.src-line{font-size:12.5px;color:var(--muted);margin-top:6px}
.src-line .lab{text-transform:uppercase;letter-spacing:.04em;font-size:10.5px;
  font-weight:700;color:#9aa5b1;margin-right:4px}
.src-line code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  background:#f2f4f7;border-radius:4px;padding:1px 5px;color:#56616d}
.clean{background:#e9f6ee;border:1px solid #cce8d6;color:#2e7d46;border-radius:10px;
  padding:16px 18px;font-size:14.5px}
footer.report{color:var(--muted);font-size:12.5px;border-top:1px solid var(--line);
  margin-top:30px;padding-top:16px}
footer.report .attribution{margin-top:6px}
footer.report a{color:var(--accent);text-decoration:none;font-weight:600}
footer.report a:hover{text-decoration:underline}
footer.report .lic{color:var(--muted)}
@media print{
  nav.tabs{position:static;display:none}
  .panel{display:block !important;page-break-inside:auto}
  header.report{background:#1f2933 !important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .panel{border-top:2px solid var(--line);padding-top:14px;margin-top:18px}
}
"""

HTML_JS = r"""
(function(){
  function show(lang){
    document.querySelectorAll('.tab').forEach(function(t){
      var on = t.getAttribute('data-lang')===lang;
      t.classList.toggle('active',on); t.setAttribute('aria-selected',on?'true':'false');
    });
    document.querySelectorAll('.panel').forEach(function(p){
      p.classList.toggle('active', p.id==='panel-'+lang);
    });
  }
  document.querySelectorAll('.tab').forEach(function(t){
    t.addEventListener('click',function(){
      var lang=t.getAttribute('data-lang'); show(lang);
      history.replaceState(null,'','#'+lang);
    });
  });
  var first=document.querySelector('.tab');
  var h=(location.hash||'').replace('#','');
  var want=h && document.querySelector('.tab[data-lang="'+h+'"]');
  show((want?h:(first?first.getAttribute('data-lang'):'')));
})();
"""


def _esc(text) -> str:
    return html.escape((text or "").strip())


def _excerpt_html(text: str, highlight: str = None) -> str:
    safe = _esc(text)
    h = (highlight or "").strip()
    if h:
        safe_h = _esc(h)
        safe = safe.replace(safe_h, f"<mark>{safe_h}</mark>", 1)
    return safe


def build_html(payload: dict) -> str:
    project = payload.get("project_name", "Translation audit")
    audit_date = payload.get("audit_date", "")
    batch = payload.get("batch_number", "")
    source_lang = payload.get("source_language", "source")
    batch_str = f"{batch:02d}" if isinstance(batch, int) else str(batch)

    grouped, lang_order = group_findings(payload.get("findings", []))
    languages = coverage_order(payload, lang_order)

    total = len(payload.get("findings", []))
    n_likely = sum(1 for f in payload.get("findings", [])
                   if normalise_bucket(f.get("bucket", "")) == "likely_error")
    n_worth = total - n_likely

    coverage = payload.get("coverage", {}) or {}
    cov_total = sum(len(v) for v in coverage.values())
    per_lang = (cov_total // len(coverage)) if coverage else 0
    findings_urls = {}
    for f in payload.get("findings", []):
        findings_urls.setdefault(f.get("language"), set()).add(f.get("url"))

    src_label = language_label(source_lang)
    target_labels = ", ".join(language_label(l) for l in languages) or "—"

    P = []
    P.append("<!doctype html>")
    P.append('<html lang="en"><head><meta charset="utf-8">')
    P.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    P.append(f"<title>{_esc(project)} — translation audit</title>")
    P.append("<style>" + HTML_CSS + "</style></head><body>")

    # Header
    P.append('<header class="report"><div class="wrap">')
    P.append(f"<h1>{_esc(project)}</h1>")
    P.append(f'<div class="sub">Translation audit · batch {_esc(batch_str)} · {_esc(audit_date)}</div>')
    P.append(f'<div class="src">Source <b>{_esc(src_label)}</b> &rarr; {_esc(target_labels)}</div>')
    P.append('<div class="chips">')
    P.append(f'<div class="chip"><span class="n">{total}</span><span class="l">findings</span></div>')
    P.append(f'<div class="chip likely"><span class="n">{n_likely}</span><span class="l">likely errors</span></div>')
    P.append(f'<div class="chip worth"><span class="n">{n_worth}</span><span class="l">worth checking</span></div>')
    P.append(f'<div class="chip"><span class="n">{len(languages)}</span><span class="l">languages</span></div>')
    P.append("</div>")
    P.append('<div class="intro">Each tab is one language version, self-contained so it can '
             'be handed to that market&rsquo;s native reviewer on its own. '
             '<b class="le">Likely errors</b> are patterns a non-native reviewer can flag '
             'confidently; <b class="wc">Worth checking</b> items could be deliberate '
             'translator choices &mdash; flagged, not asserted. Findings name the anomaly '
             'only; the reviewer decides the fix.</div>')
    if coverage:
        P.append(f'<div class="scope"><strong>Sample audit — not a complete crawl.</strong> '
                 f'{cov_total} URLs checked ({per_lang} per language across {len(coverage)} language '
                 f'versions), one page per page type. This is one batch in an ongoing series — a page with '
                 f'no finding was checked and came back clean; it does not imply the rest of the site is clean.</div>')
    P.append("</div></header>")

    P.append('<div class="wrap">')

    if not languages:
        P.append("<p>No languages audited in this batch.</p></div></body></html>")
        return "\n".join(P)

    # Tabs (first tab active by default so the report renders even without JS)
    P.append('<nav class="tabs" role="tablist">')
    for i, lang in enumerate(languages):
        c = bucket_counts(grouped, lang) if lang in grouped else {"likely_error": 0, "worth_checking": 0}
        n = c["likely_error"] + c["worth_checking"]
        badge = f'<span class="badge zero">&#10003;</span>' if n == 0 else f'<span class="badge">{n}</span>'
        active = " active" if i == 0 else ""
        P.append(f'<button class="tab{active}" role="tab" data-lang="{_esc(lang)}">'
                 f'{_esc(language_label(lang))}{badge}</button>')
    P.append("</nav>")

    # Panels (first panel active by default)
    for i, lang in enumerate(languages):
        active = " active" if i == 0 else ""
        P.append(f'<section class="panel{active}" id="panel-{_esc(lang)}" role="tabpanel">')
        P.append(f"<h2>{_esc(language_label(lang))}</h2>")
        cov = coverage.get(lang, [])
        if cov:
            fset = findings_urls.get(lang, set())
            P.append(f'<details class="coverage"><summary>Pages checked ({len(cov)})</summary><ul>')
            for u in cov:
                mark = '' if u in fset else ' <span class="ok">no issues flagged</span>'
                P.append(f'<li><a href="{_esc(u)}" target="_blank" rel="noopener">{_esc(u)}</a>{mark}</li>')
            P.append('</ul></details>')
        if lang not in grouped or not any(grouped[lang].get(b) for b in BUCKETS):
            P.append('<div class="clean">No issues flagged in this batch.</div></section>')
            continue
        c = bucket_counts(grouped, lang)
        P.append(f'<div class="langmeta">{c["likely_error"]} likely · {c["worth_checking"]} worth checking</div>')
        for bucket in BUCKETS:
            items = grouped[lang].get(bucket, [])
            if not items:
                continue
            cls = "likely" if bucket == "likely_error" else "worth"
            P.append(f'<div class="bucket {cls}"><h3>{BUCKET_LABELS[bucket]}'
                     f'<span class="count">{len(items)}</span></h3>')
            for issue in group_issues(items):
                P.append(f'<article class="finding {cls}">')
                if issue["diagnosis"]:
                    P.append(f'<div class="diag">{_esc(issue["diagnosis"])}</div>')
                if issue["shared_source"]:
                    P.append(f'<div class="src-line"><span class="lab">Source {_esc(source_lang)}</span>'
                             f'<code>{_esc(issue["shared_source"])}</code></div>')
                for inst in issue["instances"]:
                    field = FIELD_LABELS.get(inst.get("field", ""), inst.get("field", ""))
                    url = inst.get("url", "")
                    P.append('<div class="inst"><div class="head">'
                             f'<span class="field">{_esc(field)}</span>'
                             f'<a class="url" href="{_esc(url)}" target="_blank" rel="noopener">{_esc(url)}</a>'
                             "</div>")
                    P.append(f'<div class="excerpt">{_excerpt_html(inst.get("excerpt"), inst.get("highlight"))}</div>')
                    isrc = (inst.get("source_excerpt") or "").strip()
                    if isrc and not issue["shared_source"]:
                        P.append(f'<div class="src-line"><span class="lab">Source {_esc(source_lang)}</span>'
                                 f'<code>{_esc(isrc)}</code></div>')
                    P.append("</div>")
                P.append("</article>")
            P.append("</div>")
        P.append("</section>")

    P.append('<footer class="report">'
             'Generated with the '
             '<a href="https://github.com/rebelytics/translation-audit" target="_blank" rel="noopener">translation-audit skill</a>'
             ' · CC BY 4.0 · Skill created by '
             '<a href="https://rebelytics.com" target="_blank" rel="noopener">Eoghan Henn</a>'
             '</footer>')
    P.append("</div>")
    P.append("<script>" + HTML_JS + "</script>")
    P.append("</body></html>")
    return "\n".join(P)


# --------------------------------------------------------------------------
# DOCX (legacy / on request — grouped, but plainly styled)
# --------------------------------------------------------------------------

def build_docx(payload: dict, output_path: Path) -> None:
    try:
        from docx import Document
    except ImportError:
        print("ERROR: python-docx is not installed. Install with: pip install python-docx",
              file=sys.stderr)
        sys.exit(1)

    document = Document()
    project = payload.get("project_name", "Translation audit")
    audit_date = payload.get("audit_date", "")
    batch = payload.get("batch_number", "")
    source_lang = payload.get("source_language", "source")
    title = f"{project} — translation audit, batch {batch:02d}" if isinstance(batch, int) \
        else f"{project} — translation audit"

    document.add_heading(title, level=1)
    document.add_paragraph(f"Audit date: {audit_date}")
    document.add_paragraph(
        "Each section is one language version and is self-contained. Items are grouped as "
        "Likely errors (a non-native reviewer can flag confidently) and Worth checking "
        "(could be deliberate translator choices). Findings name the anomaly only."
    )

    grouped, lang_order = group_findings(payload.get("findings", []))
    languages = coverage_order(payload, lang_order)
    if not languages:
        document.add_paragraph("No languages audited in this batch.")
        document.save(output_path)
        return

    for lang in languages:
        document.add_heading(language_label(lang), level=2)
        if lang not in grouped or not any(grouped[lang].get(b) for b in BUCKETS):
            document.add_paragraph("No issues flagged in this batch.")
            continue
        for bucket in BUCKETS:
            items = grouped[lang].get(bucket, [])
            if not items:
                continue
            document.add_heading(BUCKET_LABELS[bucket], level=3)
            for issue in group_issues(items):
                if issue["diagnosis"]:
                    p = document.add_paragraph(style="List Bullet")
                    p.add_run(issue["diagnosis"])
                if issue["shared_source"]:
                    p = document.add_paragraph()
                    p.add_run(f"Source ({source_lang}): ").bold = True
                    p.add_run(f'"{issue["shared_source"]}"')
                for inst in issue["instances"]:
                    field = FIELD_LABELS.get(inst.get("field", ""), inst.get("field", ""))
                    p = document.add_paragraph()
                    p.add_run(f"{field}: ").bold = True
                    p.add_run(inst.get("url", ""))
                    p = document.add_paragraph()
                    p.add_run("Excerpt: ").bold = True
                    p.add_run(f'"{(inst.get("excerpt") or "").strip()}"')
                    isrc = (inst.get("source_excerpt") or "").strip()
                    if isrc and not issue["shared_source"]:
                        p = document.add_paragraph()
                        p.add_run(f"Source ({source_lang}): ").bold = True
                        p.add_run(f'"{isrc}"')

    document.save(output_path)


def find_findings_file(project_dir: Path, batch_number) -> Path:
    findings_dir = project_dir / "findings" / "raw"
    if not findings_dir.exists():
        return None
    if batch_number is not None:
        candidate = findings_dir / f"batch-{batch_number:02d}.json"
        return candidate if candidate.exists() else None
    candidates = sorted(findings_dir.glob("batch-*.json"))
    return candidates[-1] if candidates else None


def main():
    parser = argparse.ArgumentParser(description="Build the audit deliverable from a findings JSON.")
    parser.add_argument("--findings", default=None,
                        help="Path to the findings JSON. If omitted, the latest "
                             "batch-NN.json under findings/raw/ is used.")
    parser.add_argument("--project-dir", default=".",
                        help="Path to the audit project folder.")
    parser.add_argument("--batch-number", type=int, default=None,
                        help="Pick a specific batch from findings/raw/ instead of the latest.")
    parser.add_argument("--format", default="html,md",
                        help="Comma-separated formats: html, md, docx (default 'html,md'). "
                             "docx requires python-docx and is opt-in.")
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    if args.findings:
        findings_path = Path(args.findings)
    else:
        findings_path = find_findings_file(project_dir, args.batch_number)
        if not findings_path:
            print("ERROR: no findings JSON found under findings/raw/. "
                  "Pass --findings explicitly.", file=sys.stderr)
            sys.exit(1)

    with open(findings_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    audit_date = payload.get("audit_date", "")
    batch = payload.get("batch_number", 0)
    batch_str = f"{batch:02d}" if isinstance(batch, int) else str(batch)
    stem = f"audit-{audit_date}-batch-{batch_str}"
    output_dir = project_dir / "findings"
    output_dir.mkdir(parents=True, exist_ok=True)

    formats = [f.strip().lower() for f in args.format.split(",") if f.strip()]

    if "html" in formats:
        html_path = output_dir / f"{stem}.html"
        html_path.write_text(build_html(payload), encoding="utf-8")
        print(f"Wrote {html_path}", file=sys.stderr)

    if "md" in formats:
        md_path = output_dir / f"{stem}.md"
        md_path.write_text(build_markdown(payload), encoding="utf-8")
        print(f"Wrote {md_path}", file=sys.stderr)

    if "docx" in formats:
        docx_path = output_dir / f"{stem}.docx"
        build_docx(payload, docx_path)
        print(f"Wrote {docx_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
