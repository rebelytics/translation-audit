#!/usr/bin/env python3
"""
build_audit_doc.py — assemble the audit deliverable (.docx + .md) from
a findings JSON.

The audit doc is a **reviewer-facing artefact**: it presents findings
TO a native speaker so they can decide which to fix. It must not
attribute any verdict to a native reviewer who has not seen the
document yet. Verdict state (review_status / review_note / reviewer)
is captured AFTER native review via apply_verdicts.py and lives in
the findings JSON, but is deliberately not rendered in this
deliverable; it feeds downstream artefacts (e.g. a fix list) that are
out of scope for this script.

Findings JSON shape:

  {
    "project_name": "example-com-audit",
    "audit_date": "2026-05-28",
    "batch_number": 1,
    "source_language": "en",
    "audited_languages": ["de", "fr", "es"],   # optional but recommended
    "findings": [
      {
        "language": "de",
        "url": "https://example.com/de/produkt",
        "field": "meta_description",          # or "title" / "h1" / "body"
        "excerpt": "...",                     # exact text from the page
        "diagnosis": "...",                   # 1-2 sentence diagnosis
        "bucket": "likely_error",             # or "worth_checking"
        "source_excerpt": null,               # or the source-language equivalent
        "sub_type": null,                     # "dom_only_not_rendered"
                                              # or "visibility_unconfirmed"
        "review_status": "unreviewed",        # captured post-review only
        "review_note": null,                  # captured post-review only
        "reviewer": null                      # "native_speaker" once reviewed
      },
      ...
    ]
  }

Body sub-types influence how the diagnosis is prefixed in the doc:

  - "dom_only_not_rendered"   → diagnosis prefixed with "[DOM-only, not
                                rendered]". The excerpt was extracted
                                from a hidden/template container in the
                                raw HTML.
  - "visibility_unconfirmed"  → diagnosis prefixed with "[Visibility
                                unconfirmed — verify on rendered page]".
                                The excerpt was extracted from raw HTML
                                with no rendered-text confirmation, so
                                the reviewer should verify it actually
                                appears on the page.

A language listed in `audited_languages` but with zero findings still
gets a section in the doc that reads "No issues flagged in this
batch." — coverage (what was checked) and findings (what was wrong) are
reported independently.

Output:
  findings/audit-YYYY-MM-DD-batch-NN.docx
  findings/audit-YYYY-MM-DD-batch-NN.md

Both files are written by default. Use --format docx or --format md to
restrict output.

Usage:
  python build_audit_doc.py --findings findings/raw/batch-01.json \\
      --project-dir ./my-audit
"""

import argparse
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
    "hu": "Hungarian",
    "it": "Italian",
    "nl": "Dutch", "be": "Dutch (Belgium)",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sv": "Swedish", "se": "Swedish",
    "tr": "Turkish",
    "zh": "Chinese",
    "ja": "Japanese",
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

# Sub-type prefixes for body-layer findings. Render in front of the
# diagnosis so the reviewer can scan the visibility caveat at a glance.
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
    """Group by language → bucket → list of findings.

    Returns (grouped, lang_order). Languages appear in the order they
    are first seen in the findings list; the caller can extend this
    with audited_languages to surface clean coverage.
    """
    grouped = defaultdict(lambda: defaultdict(list))
    lang_order = []
    for f in findings:
        lang = f.get("language", "unknown")
        bucket = normalise_bucket(f.get("bucket", "worth_checking"))
        if lang not in grouped:
            lang_order.append(lang)
        grouped[lang][bucket].append(f)
    return grouped, lang_order


def coverage_order(payload: dict, lang_order: list) -> list:
    """Combined ordering of languages to render — findings-bearing
    languages first (in discovery order), then any audited_languages
    with no findings, so coverage is visible in the doc."""
    audited = [c for c in (payload.get("audited_languages") or [])
               if c not in lang_order]
    return list(lang_order) + audited


def render_finding_markdown(out: list, finding: dict, source_lang: str) -> None:
    """Append the markdown bullets for one finding to `out`."""
    url = finding.get("url", "")
    field = FIELD_LABELS.get(finding.get("field", ""), finding.get("field", ""))
    excerpt = (finding.get("excerpt") or "").strip()
    diagnosis = diagnosis_with_prefix(finding)
    source_excerpt = (finding.get("source_excerpt") or "").strip() if finding.get("source_excerpt") else ""

    out.append(f"- **URL:** {url}")
    out.append(f"  **Field:** {field}")
    if source_excerpt:
        out.append(f"  **Source ({source_lang}):** \"{source_excerpt}\"")
    out.append(f"  **Excerpt:** \"{excerpt}\"")
    out.append(f"  **Diagnosis:** {diagnosis}")
    out.append("")


def build_markdown(payload: dict) -> str:
    """Build the markdown audit doc."""
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
        "Each section below covers one language version and is self-contained, so it "
        "can be handed to the native speaker responsible for that site without context "
        "from the other sections. Within each section, items are grouped as **Likely "
        "errors** (patterns even a non-native reviewer can flag confidently) and **Worth "
        "checking** (items that look off but could be deliberate translator choices — "
        "flagged for review rather than asserted as bugs). Both categories should be "
        "sanity-checked by the native speaker before fixing."
    )
    out.append("")

    grouped, lang_order = group_findings(payload.get("findings", []))
    languages = coverage_order(payload, lang_order)

    if not languages:
        out.append("_No languages audited in this batch._")
        out.append("")
        return "\n".join(out)

    for lang in languages:
        out.append(f"## {language_label(lang)}")
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
            for f in items:
                render_finding_markdown(out, f, source_lang)

    return "\n".join(out)


def build_docx(payload: dict, output_path: Path) -> None:
    """Build the .docx audit doc using python-docx."""
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
        "Each section below covers one language version and is self-contained, so it "
        "can be handed to the native speaker responsible for that site without context "
        "from the other sections. Within each section, items are grouped as Likely "
        "errors (patterns even a non-native reviewer can flag confidently) and Worth "
        "checking (items that look off but could be deliberate translator choices — "
        "flagged for review rather than asserted as bugs). Both categories should be "
        "sanity-checked by the native speaker before fixing."
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
            for f in items:
                url = f.get("url", "")
                field = FIELD_LABELS.get(f.get("field", ""), f.get("field", ""))
                excerpt = (f.get("excerpt") or "").strip()
                diagnosis = diagnosis_with_prefix(f)
                source_excerpt = (f.get("source_excerpt") or "").strip() \
                    if f.get("source_excerpt") else ""

                p = document.add_paragraph(style="List Bullet")
                p.add_run(url)

                p = document.add_paragraph()
                p.add_run("Field: ").bold = True
                p.add_run(field)

                if source_excerpt:
                    p = document.add_paragraph()
                    p.add_run(f"Source ({source_lang}): ").bold = True
                    p.add_run(f'"{source_excerpt}"')

                p = document.add_paragraph()
                p.add_run("Excerpt: ").bold = True
                p.add_run(f'"{excerpt}"')

                p = document.add_paragraph()
                p.add_run("Diagnosis: ").bold = True
                p.add_run(diagnosis)

    document.save(output_path)


def find_findings_file(project_dir: Path, batch_number) -> Path:
    """Locate the latest findings JSON for the given batch, or any batch
    if not specified. Looks under findings/raw/batch-NN.json — the
    canonical input location."""
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
    parser.add_argument("--format", default="docx,md",
                        help="Comma-separated list of formats to produce (default 'docx,md').")
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
