#!/usr/bin/env python3
"""
apply_verdicts.py — patch native-reviewer verdicts onto a findings JSON.

This is the post-review step. The native speaker reads the audit doc
(produced by build_audit_doc.py), decides which findings are real and
which are deliberate translator choices, fills out a verdict CSV, and
this script merges those verdicts into the findings JSON.

The audit doc itself does not show verdicts — by design. It is INPUT
to native review, not output of it. The verdict state captured here
feeds downstream artefacts (e.g. a fix list for the dev team) rather
than altering the original audit deliverable.

Verdict CSV schema:

    url, field, excerpt, review_status, review_note

  - url:           the URL the finding is on
  - field:         title / meta_description / h1 / body
  - excerpt:       the exact excerpt from the audit doc (used to
                   disambiguate multiple findings on the same
                   URL/field combination)
  - review_status: confirmed | dismissed | edited
  - review_note:   optional free-text rationale (or the native
                   speaker's edit, when review_status is "edited")

The script matches each verdict row to a finding by (url, field,
excerpt). Mismatches are reported and never silently overwrite
anything. By default the script writes the patched JSON back to the
same file; use --output to write to a different path.

After patching, the findings JSON has review_status / review_note /
reviewer set on the reviewed findings. The `reviewer` field is set to
"native_speaker" automatically — this script only ever applies human
review, never agent self-judgments.

Usage:
  python apply_verdicts.py --findings findings/raw/batch-01.json \\
      --verdicts native-verdicts-batch-01.csv

  python apply_verdicts.py --findings findings/raw/batch-01.json \\
      --verdicts native-verdicts-batch-01.csv \\
      --output findings/raw/batch-01.patched.json
"""

import argparse
import csv
import json
import sys
from pathlib import Path

VALID_VERDICTS = {"unreviewed", "confirmed", "dismissed", "edited"}
REQUIRED_VERDICT_COLUMNS = ("url", "field", "excerpt", "review_status")
REVIEWER_TAG = "native_speaker"


def normalise(value):
    """Strip and lowercase nothing — just strip whitespace. Excerpt
    comparisons are exact by design; if the reviewer's CSV has trailing
    whitespace they didn't intend, we want to report that as a
    mismatch rather than silently absorb it."""
    if value is None:
        return ""
    return str(value).strip()


def finding_key(finding):
    return (
        normalise(finding.get("url")),
        normalise(finding.get("field")),
        normalise(finding.get("excerpt")),
    )


def verdict_key(row):
    return (
        normalise(row.get("url")),
        normalise(row.get("field")),
        normalise(row.get("excerpt")),
    )


def load_verdicts(path: Path):
    """Read the verdict CSV. Returns (rows, errors)."""
    rows = []
    errors = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = [c.strip() for c in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED_VERDICT_COLUMNS if c not in fieldnames]
        if missing:
            errors.append(
                f"Missing required columns in {path}: {', '.join(missing)}. "
                f"Required columns: {', '.join(REQUIRED_VERDICT_COLUMNS)}."
            )
            return rows, errors
        for line_no, raw_row in enumerate(reader, start=2):  # start=2 accounts for header
            row = {k: normalise(v) for k, v in raw_row.items()}
            verdict = row.get("review_status", "").lower()
            if verdict not in VALID_VERDICTS:
                errors.append(
                    f"{path}:{line_no}: invalid review_status "
                    f"{verdict!r}. Must be one of: {', '.join(sorted(VALID_VERDICTS))}."
                )
                continue
            row["review_status"] = verdict
            row["_line_no"] = line_no
            rows.append(row)
    return rows, errors


def apply_verdicts(payload: dict, verdict_rows: list):
    """Apply verdicts in-place on payload['findings']. Returns a tuple
    (applied, unmatched, ambiguous):

      - applied:   list of (line_no, key) tuples that were applied
      - unmatched: list of (line_no, key) tuples with no matching finding
      - ambiguous: list of (line_no, key) tuples that matched multiple
                   findings (no patch applied; user must disambiguate)
    """
    findings = payload.get("findings", [])

    # Build an index from key → list of finding indices, so we can detect
    # ambiguous matches (same url + field + excerpt on multiple findings).
    index = {}
    for i, f in enumerate(findings):
        index.setdefault(finding_key(f), []).append(i)

    applied = []
    unmatched = []
    ambiguous = []

    for row in verdict_rows:
        key = verdict_key(row)
        line_no = row.get("_line_no")
        matches = index.get(key, [])
        if not matches:
            unmatched.append((line_no, key))
            continue
        if len(matches) > 1:
            ambiguous.append((line_no, key))
            continue
        idx = matches[0]
        findings[idx]["review_status"] = row["review_status"]
        findings[idx]["reviewer"] = REVIEWER_TAG
        note = row.get("review_note") or None
        # Only set review_note if the row actually provided a value;
        # don't overwrite an existing note with empty string.
        if note:
            findings[idx]["review_note"] = note
        applied.append((line_no, key))

    return applied, unmatched, ambiguous


def main():
    parser = argparse.ArgumentParser(
        description="Apply native-reviewer verdicts to a findings JSON. The audit doc "
                    "produced by build_audit_doc.py is INPUT to native review; this "
                    "script captures the OUTPUT of that review."
    )
    parser.add_argument(
        "--findings",
        required=True,
        help="Path to the findings JSON to patch.",
    )
    parser.add_argument(
        "--verdicts",
        required=True,
        help="Path to the verdict CSV.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the patched JSON. Defaults to the input path "
        "(overwrite in place).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report matches and mismatches without writing the JSON.",
    )
    args = parser.parse_args()

    findings_path = Path(args.findings)
    verdicts_path = Path(args.verdicts)
    output_path = Path(args.output) if args.output else findings_path

    if not findings_path.exists():
        print(f"ERROR: findings file not found: {findings_path}", file=sys.stderr)
        sys.exit(1)
    if not verdicts_path.exists():
        print(f"ERROR: verdict CSV not found: {verdicts_path}", file=sys.stderr)
        sys.exit(1)

    with open(findings_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    verdict_rows, errors = load_verdicts(verdicts_path)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        if not verdict_rows:
            sys.exit(1)

    applied, unmatched, ambiguous = apply_verdicts(payload, verdict_rows)

    # Reporting
    total_rows = len(verdict_rows)
    total_findings = len(payload.get("findings", []))
    print(
        f"Verdict CSV: {total_rows} row(s). Findings JSON: {total_findings} finding(s).",
        file=sys.stderr,
    )
    print(f"Applied:   {len(applied)}", file=sys.stderr)
    print(f"Unmatched: {len(unmatched)}", file=sys.stderr)
    print(f"Ambiguous: {len(ambiguous)}", file=sys.stderr)

    if unmatched:
        print("\nUnmatched verdict rows (no finding with this url+field+excerpt):",
              file=sys.stderr)
        for line_no, key in unmatched:
            url, field, excerpt = key
            short_excerpt = (excerpt[:80] + "…") if len(excerpt) > 80 else excerpt
            print(f"  line {line_no}: url={url!r} field={field!r} excerpt={short_excerpt!r}",
                  file=sys.stderr)

    if ambiguous:
        print("\nAmbiguous verdict rows (matched more than one finding — disambiguate by "
              "trimming or extending the excerpt):", file=sys.stderr)
        for line_no, key in ambiguous:
            url, field, excerpt = key
            short_excerpt = (excerpt[:80] + "…") if len(excerpt) > 80 else excerpt
            print(f"  line {line_no}: url={url!r} field={field!r} excerpt={short_excerpt!r}",
                  file=sys.stderr)

    if args.dry_run:
        print("\nDry run — JSON not written.", file=sys.stderr)
        # Exit non-zero if there were unmatched or ambiguous rows so
        # callers can detect issues programmatically.
        sys.exit(1 if (unmatched or ambiguous) else 0)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\nWrote patched JSON to {output_path}", file=sys.stderr)

    # Exit non-zero if any rows didn't apply cleanly, so wrapping
    # scripts know to surface the report.
    sys.exit(1 if (unmatched or ambiguous) else 0)


if __name__ == "__main__":
    main()
