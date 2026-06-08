#!/usr/bin/env python3
"""
state.py — three-list lifecycle bookkeeping for a translation audit
project.

The skill's core operations move URLs in one direction through four
CSV files:

    open.csv   →   audited.csv   →   verified.csv
                       │
                       └─→   open.csv (when a fix introduces a new issue)

    excluded.csv (anything deliberately removed from scope)

Every transition is an atomic operation: read the source file, take
the rows that match the keys, write them to the destination with any
added columns, write the source back without those rows. No row ever
appears in two files at once.

This script bundles those operations so the agent doesn't reimplement
them per batch — that's where schema drift creeps in.

Commands:

  init      Create the four state CSVs from assets/*.template if they
            don't already exist. Safe to run multiple times.

  move      Move rows from one state list to another by URL. Optionally
            add named columns with values (e.g. audit_date, audit_file).
            See --add for the syntax.

  exclude   Move rows from any state list to excluded.csv with a reason.

  reaudit   Move rows from audited.csv (or verified.csv) back to
            open.csv, optionally with a note explaining why.

  status    Print the current row counts per state file (and write them
            to <project>/README.md).

  validate  Check the state CSVs against the template schemas and report
            any column drift. Read-only.

Usage examples:

  python state.py init --project-dir ./my-audit

  python state.py move --project-dir ./my-audit \\
      --from open --to audited \\
      --urls-file batch-01-urls.txt \\
      --add audit_date=2026-05-28 \\
      --add audit_file=findings/audit-2026-05-28-batch-01.docx

  python state.py exclude --project-dir ./my-audit \\
      --urls https://example.com/redirect/legacy \\
      --reason "Server redirect, not a real page"

  python state.py status --project-dir ./my-audit
"""

import argparse
import csv
import datetime
import shutil
import sys
from pathlib import Path

STATE_FILES = {
    "open": "open.csv",
    "audited": "audited.csv",
    "verified": "verified.csv",
    "excluded": "excluded.csv",
}

# Schema columns per state list, as defined by assets/*.template.
TEMPLATE_COLUMNS = {
    "open": ["url", "language", "canonical_url", "page_type",
             "priority_score", "notes"],
    "audited": ["url", "language", "canonical_url", "page_type",
                "priority_score", "notes", "audit_date", "audit_file",
                "verify_attempts"],
    "verified": ["url", "language", "canonical_url", "page_type",
                 "priority_score", "notes", "audit_date", "audit_file",
                 "verified_date"],
    "excluded": ["url", "language", "canonical_url", "page_type",
                 "reason", "excluded_date"],
}

# Where the templates live in the skill repo. The script discovers them
# relative to its own location so it works whether invoked from the
# repo or from an installed copy.
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPT_DIR.parent / "assets"


def project_state_dir(project_dir: Path) -> Path:
    return project_dir / "urls"


def state_path(project_dir: Path, name: str) -> Path:
    if name not in STATE_FILES:
        raise ValueError(f"Unknown state list: {name!r}. "
                         f"Expected one of {sorted(STATE_FILES)}.")
    return project_state_dir(project_dir) / STATE_FILES[name]


def template_path(name: str) -> Path:
    return TEMPLATES_DIR / f"{STATE_FILES[name]}.template"


def read_rows(path: Path):
    """Read a CSV into (header, rows). Returns ([], []) if missing."""
    if not path.exists():
        return [], []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    return header, rows


def write_rows(path: Path, header: list, rows: list) -> None:
    """Write rows back, preserving header order. Rows missing a column
    write the empty string; rows with extra columns drop them."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in header})


def cmd_init(args) -> int:
    """Create the four state CSVs from the asset templates if missing."""
    project_dir = Path(args.project_dir)
    state_dir = project_state_dir(project_dir)
    state_dir.mkdir(parents=True, exist_ok=True)

    created, skipped = [], []
    for name in STATE_FILES:
        target = state_path(project_dir, name)
        if target.exists():
            skipped.append(target)
            continue
        src = template_path(name)
        if src.exists():
            shutil.copy2(src, target)
        else:
            # No template? Write a header-only file from TEMPLATE_COLUMNS.
            with open(target, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=TEMPLATE_COLUMNS[name])
                writer.writeheader()
        created.append(target)

    for p in created:
        print(f"Created {p}", file=sys.stderr)
    for p in skipped:
        print(f"Already exists, skipping: {p}", file=sys.stderr)
    return 0


def parse_add_pairs(values) -> dict:
    """Parse --add key=value pairs into a dict."""
    out = {}
    for v in values or []:
        if "=" not in v:
            raise ValueError(f"--add value must be key=value, got {v!r}")
        k, val = v.split("=", 1)
        out[k.strip()] = val.strip()
    return out


def load_urls(args) -> set:
    """Collect URLs from --urls and --urls-file. Returns a set."""
    urls = set(args.urls or [])
    if args.urls_file:
        with open(args.urls_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.add(line)
    return urls


def cmd_move(args) -> int:
    """Move rows from one state list to another, with optional added columns."""
    project_dir = Path(args.project_dir)
    src = state_path(project_dir, args.from_)
    dst = state_path(project_dir, args.to)
    if src == dst:
        print("ERROR: --from and --to are the same list.", file=sys.stderr)
        return 2

    urls = load_urls(args)
    if not urls:
        print("ERROR: no URLs to move. Pass --urls or --urls-file.", file=sys.stderr)
        return 2

    src_header, src_rows = read_rows(src)
    if not src_rows:
        print(f"WARNING: {src} is empty or missing — nothing to move.", file=sys.stderr)
        return 1

    dst_header, dst_rows = read_rows(dst)
    if not dst_header:
        dst_header = TEMPLATE_COLUMNS[args.to]

    add_pairs = parse_add_pairs(args.add)
    # Ensure any added columns exist in the destination header.
    for col in add_pairs:
        if col not in dst_header:
            dst_header.append(col)

    keep_rows = []
    moved = 0
    matched_urls = set()
    for row in src_rows:
        url = row.get("url", "")
        if url in urls:
            new_row = dict(row)
            new_row.update(add_pairs)
            dst_rows.append(new_row)
            moved += 1
            matched_urls.add(url)
        else:
            keep_rows.append(row)

    write_rows(src, src_header, keep_rows)
    write_rows(dst, dst_header, dst_rows)

    missing = urls - matched_urls
    print(f"Moved {moved} row(s) from {src.name} to {dst.name}.", file=sys.stderr)
    if missing:
        print(f"  {len(missing)} URL(s) not found in {src.name}:", file=sys.stderr)
        for u in sorted(missing)[:10]:
            print(f"    {u}", file=sys.stderr)
        if len(missing) > 10:
            print(f"    … and {len(missing) - 10} more", file=sys.stderr)
    if args.regen_readme:
        regenerate_readme(project_dir)
    return 0 if not missing else 1


def cmd_exclude(args) -> int:
    """Move rows from any state list to excluded.csv with a reason."""
    project_dir = Path(args.project_dir)
    urls = load_urls(args)
    if not urls:
        print("ERROR: no URLs to exclude. Pass --urls or --urls-file.", file=sys.stderr)
        return 2
    if not args.reason:
        print("ERROR: --reason is required for exclude (audit trail).", file=sys.stderr)
        return 2

    today = datetime.date.today().isoformat()
    excluded_path = state_path(project_dir, "excluded")
    excluded_header, excluded_rows = read_rows(excluded_path)
    if not excluded_header:
        excluded_header = TEMPLATE_COLUMNS["excluded"]

    total_moved = 0
    for name in ("open", "audited", "verified"):
        path = state_path(project_dir, name)
        header, rows = read_rows(path)
        if not rows:
            continue
        keep = []
        for row in rows:
            url = row.get("url", "")
            if url in urls:
                excluded_rows.append({
                    "url": url,
                    "language": row.get("language", ""),
                    "canonical_url": row.get("canonical_url", ""),
                    "page_type": row.get("page_type", ""),
                    "reason": args.reason,
                    "excluded_date": today,
                })
                total_moved += 1
            else:
                keep.append(row)
        write_rows(path, header, keep)

    write_rows(excluded_path, excluded_header, excluded_rows)
    print(f"Excluded {total_moved} URL(s).", file=sys.stderr)
    if args.regen_readme:
        regenerate_readme(project_dir)
    return 0


def cmd_reaudit(args) -> int:
    """Move rows from audited/verified back to open, e.g. for re-audit
    after a fix is discovered to have introduced a new issue."""
    project_dir = Path(args.project_dir)
    urls = load_urls(args)
    if not urls:
        print("ERROR: no URLs. Pass --urls or --urls-file.", file=sys.stderr)
        return 2

    open_path = state_path(project_dir, "open")
    open_header, open_rows = read_rows(open_path)
    if not open_header:
        open_header = TEMPLATE_COLUMNS["open"]

    total_moved = 0
    note_prefix = (args.note or "").strip()
    for name in ("audited", "verified"):
        path = state_path(project_dir, name)
        header, rows = read_rows(path)
        if not rows:
            continue
        keep = []
        for row in rows:
            url = row.get("url", "")
            if url in urls:
                new_row = {col: row.get(col, "") for col in open_header}
                if note_prefix:
                    existing_note = (row.get("notes") or "").strip()
                    new_row["notes"] = (note_prefix + "; " + existing_note).rstrip("; ")
                open_rows.append(new_row)
                total_moved += 1
            else:
                keep.append(row)
        write_rows(path, header, keep)

    write_rows(open_path, open_header, open_rows)
    print(f"Re-queued {total_moved} URL(s) into open.csv.", file=sys.stderr)
    if args.regen_readme:
        regenerate_readme(project_dir)
    return 0


def state_counts(project_dir: Path) -> dict:
    """Return a dict of {state_name: row_count}."""
    counts = {}
    for name in STATE_FILES:
        _, rows = read_rows(state_path(project_dir, name))
        counts[name] = len(rows)
    return counts


def regenerate_readme(project_dir: Path) -> None:
    """Write or refresh <project>/README.md with current state counts."""
    counts = state_counts(project_dir)
    total = sum(counts.values())
    today = datetime.date.today().isoformat()
    project_name = project_dir.name
    lines = [
        f"# {project_name}",
        "",
        f"Translation audit project. Last updated: {today}.",
        "",
        "## State (URL counts)",
        "",
        f"- Open queue: **{counts['open']}**",
        f"- Audited (awaiting fix / verification): **{counts['audited']}**",
        f"- Verified (fixes confirmed live): **{counts['verified']}**",
        f"- Excluded (out of scope): **{counts['excluded']}**",
        f"- Total tracked: **{total}**",
        "",
        "## Files",
        "",
        "- `config.yml` — project configuration",
        "- `urls/open.csv` / `audited.csv` / `verified.csv` / `excluded.csv` — state lists",
        "- `data/` — cached live page content per batch",
        "- `findings/raw/batch-NN.json` — raw findings input to the audit doc",
        "- `findings/audit-YYYY-MM-DD-batch-NN.{docx,md}` — reviewer-facing deliverables",
        "- `prioritisation/inputs/` — user-supplied prioritisation data",
        "- `prioritisation/notes.md` — how priority scoring was built",
        "",
    ]
    (project_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def cmd_status(args) -> int:
    project_dir = Path(args.project_dir)
    counts = state_counts(project_dir)
    print(f"State for project {project_dir}:")
    for name, count in counts.items():
        print(f"  {name:8s} {count}")
    if args.regen_readme:
        regenerate_readme(project_dir)
        print(f"\nWrote README at {project_dir / 'README.md'}", file=sys.stderr)
    return 0


def cmd_validate(args) -> int:
    """Check state CSV headers against the template schemas."""
    project_dir = Path(args.project_dir)
    problems = 0
    for name, expected in TEMPLATE_COLUMNS.items():
        path = state_path(project_dir, name)
        header, _ = read_rows(path)
        if not header:
            print(f"  {name}: file missing or empty — run 'state.py init'.")
            problems += 1
            continue
        missing = [c for c in expected if c not in header]
        extra = [c for c in header if c not in expected]
        status = "OK" if not missing and not extra else "DRIFT"
        print(f"  {name:8s} {status}")
        if missing:
            print(f"    Missing columns: {missing}")
            problems += 1
        if extra:
            print(f"    Extra columns (kept, but check intent): {extra}")
    return 0 if problems == 0 else 1


def main():
    p = argparse.ArgumentParser(
        description="Three-list lifecycle bookkeeping for a translation audit project."
    )
    p.add_argument("--project-dir", default=".", help="Audit project folder.")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="Create state CSVs from asset templates.")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("move", help="Move rows between state lists.")
    sp.add_argument("--from", dest="from_", required=True,
                    choices=sorted(STATE_FILES), help="Source state list.")
    sp.add_argument("--to", required=True,
                    choices=sorted(STATE_FILES), help="Destination state list.")
    sp.add_argument("--urls", action="append", default=[],
                    help="URL to move (repeatable).")
    sp.add_argument("--urls-file", default=None,
                    help="Text file with one URL per line.")
    sp.add_argument("--add", action="append", default=[],
                    help="Column to add on the destination side, key=value. Repeatable.")
    sp.add_argument("--regen-readme", action="store_true",
                    help="Regenerate the project README counts after moving.")
    sp.set_defaults(func=cmd_move)

    sp = sub.add_parser("exclude", help="Move URLs to excluded.csv with a reason.")
    sp.add_argument("--urls", action="append", default=[],
                    help="URL to exclude (repeatable).")
    sp.add_argument("--urls-file", default=None,
                    help="Text file with one URL per line.")
    sp.add_argument("--reason", required=True,
                    help="Reason for exclusion (required, kept in excluded.csv).")
    sp.add_argument("--regen-readme", action="store_true",
                    help="Regenerate the project README counts after excluding.")
    sp.set_defaults(func=cmd_exclude)

    sp = sub.add_parser("reaudit",
                        help="Move URLs from audited/verified back to open.csv.")
    sp.add_argument("--urls", action="append", default=[],
                    help="URL to re-audit (repeatable).")
    sp.add_argument("--urls-file", default=None,
                    help="Text file with one URL per line.")
    sp.add_argument("--note", default=None,
                    help="Prefix added to the URL's 'notes' column on re-queue.")
    sp.add_argument("--regen-readme", action="store_true",
                    help="Regenerate the project README counts after re-queuing.")
    sp.set_defaults(func=cmd_reaudit)

    sp = sub.add_parser("status", help="Print state counts.")
    sp.add_argument("--regen-readme", action="store_true",
                    help="Also rewrite the project README with the current counts.")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("validate", help="Check state CSV schemas against templates.")
    sp.set_defaults(func=cmd_validate)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
