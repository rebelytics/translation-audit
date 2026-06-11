#!/usr/bin/env python3
"""
fetch_pages.py — fetch live page content for the next batch of URLs.

For each URL in the batch this script captures:
  - status: HTTP status code
  - final_url: URL after redirects
  - title: contents of <title>
  - meta_description: contents of <meta name="description">
  - h1: text of the first <h1>
  - body_text: visible text from <main>/<article>, falling back to
    <body> minus <header>/<footer>/<nav>/<aside>/<script>/<style>
  - lang_attr: the lang attribute on <html>

For each non-source-language URL, the script also fetches the
source-language equivalent (from canonical_url in open.csv) so that
Phase 5 of the skill can compare them. Source pages are cached within
the same batch so we don't refetch the same canonical URL multiple
times.

Output is written to data/pages-{lang}-batch-N.json — one file per
target language, with an array of objects per URL.

Usage:
  python fetch_pages.py --project-dir ./my-audit --batch-size 20

Or, in environments without HTTP access, ingest a pre-extracted CSV:
  python fetch_pages.py --project-dir ./my-audit --from-csv ./sf-export.csv

Run with --help for full options.
"""

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


DEFAULT_USER_AGENT = "translation-audit/1.0 (+https://github.com/rebelytics/translation-audit)"
WHITESPACE_RE = re.compile(r"\s+")


def fetch_html(url: str, timeout: int = 30, user_agent: str = DEFAULT_USER_AGENT):
    """Fetch a URL and return (html_text, status_code, final_url).

    Follows redirects. Returns (None, status, final_url) on non-200
    responses.
    """
    headers = {"User-Agent": user_agent, "Accept": "text/html"}
    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    final_url = response.url
    if response.status_code != 200:
        return None, response.status_code, final_url
    return response.text, response.status_code, final_url


def clean_text(value: str) -> str:
    """Strip and collapse all internal whitespace (newlines, tabs, runs of
    spaces) to single spaces. Templates often produce raw newline+tab runs
    inside title/H1/meta content; without uniform cleaning those surface
    in audit findings as "broken" text when in fact they are markup
    artefacts identical across all language versions."""
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", value).strip()


# CSS rules in inline `style` attributes that mark a container hidden.
_INLINE_HIDDEN_PATTERNS = ("display:none", "display: none",
                          "visibility:hidden", "visibility: hidden")


def _is_inline_hidden(el) -> bool:
    """True if the element's inline `style` attribute hides it.

    bs4 >= 4.13 can surface already-decomposed elements (attrs=None) in
    a find_all(style=True) scan that runs after earlier decompose()
    passes; treat those as not-hidden instead of crashing on .get().
    """
    if getattr(el, "attrs", None) is None:
        return False
    style = (el.get("style") or "").lower().replace(" ", "")
    return any(p.replace(" ", "") in style for p in _INLINE_HIDDEN_PATTERNS)


def drop_non_visible_containers(root) -> None:
    """Remove containers from the body subtree that are demonstrably
    non-visible from raw HTML inspection. Mutates `root` in place.

    Drops (per Phase 4 of the skill):
      - <template> subtrees (never rendered)
      - elements with the [hidden] attribute
      - elements with aria-hidden="true"
      - elements with inline style="display:none" / "visibility:hidden"

    These heuristics do not catch JS-injected hidden state or
    CSS-class-driven display:none — for those, the rendered-text
    browser pass is the remedy. But they materially reduce the
    false-positive rate on the raw-HTTP body extraction path.
    """
    # <template> subtrees first — they may contain otherwise-valid markup
    # that we don't want to harvest text from.
    for el in root.find_all("template"):
        el.decompose()

    # [hidden] attribute (HTML5 boolean).
    for el in root.find_all(attrs={"hidden": True}):
        el.decompose()

    # aria-hidden="true".
    for el in root.find_all(attrs={"aria-hidden": "true"}):
        el.decompose()

    # Inline style hiding.
    for el in list(root.find_all(style=True)):
        if _is_inline_hidden(el):
            el.decompose()


def extract_fields(html: str) -> dict:
    """Extract title, meta description, H1, body text, and html-lang.

    Whitespace is normalised uniformly across all extracted fields, not
    just body_text — title and H1 are commonly produced by templates
    with raw newline + tab runs that would otherwise surface in findings.
    """
    soup = BeautifulSoup(html, "html.parser")

    # <title>
    title_el = soup.find("title")
    title = clean_text(title_el.get_text(" ") if title_el else "")

    # <meta name="description">
    meta_desc = ""
    meta_el = soup.find("meta", attrs={"name": "description"})
    if meta_el and meta_el.get("content"):
        meta_desc = clean_text(meta_el["content"])

    # First <h1>. An H1 is a rendered element: templates hide parts of
    # it with CSS (e.g. a duplicate artist-name span kept for layout),
    # so apply the same hidden-container drops inside the h1 subtree
    # before reading it. CSS-class-driven hiding is still invisible on
    # this raw path — h1 findings that allege visible-composition
    # defects (duplicated text, leaked template strings) need the
    # rendered check before they may ship as Likely errors.
    h1_el = soup.find("h1")
    if h1_el is not None:
        drop_non_visible_containers(h1_el)
    h1 = clean_text(h1_el.get_text(" ") if h1_el else "")

    # <html lang="...">
    html_el = soup.find("html")
    lang_attr = (html_el.get("lang", "") if html_el else "").strip()

    # Body text — prefer <main> or <article>, fall back to <body>.
    body_root = soup.find("main") or soup.find("article") or soup.find("body")
    if body_root:
        # Strip noise elements before extracting text. First the obvious
        # template/chrome tags, then the visibility-hidden containers
        # documented in the skill's Phase 4 mitigations.
        for tag_name in ("header", "footer", "nav", "aside",
                         "script", "style", "noscript", "form"):
            for el in body_root.find_all(tag_name):
                el.decompose()
        drop_non_visible_containers(body_root)
        body_text = clean_text(body_root.get_text(separator=" "))
    else:
        body_text = ""

    return {
        "title": title,
        "meta_description": meta_desc,
        "h1": h1,
        "lang_attr": lang_attr,
        "body_text": body_text,
    }


def read_open_csv(open_csv: Path):
    """Read the open queue and return all rows as a list of dicts."""
    with open(open_csv, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def read_from_csv_input(path: Path):
    """
    Read pre-extracted page content from an external CSV (e.g., a
    Screaming Frog export). The CSV must have these columns (case-
    insensitive header match):

      url, language, canonical_url, status, title,
      meta_description, h1, body_text, lang_attr

    Missing columns are treated as empty strings.
    """
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Lowercase the header map for case-insensitive access
        return [{k.lower(): (v or "") for k, v in row.items()} for row in reader]


def fetch_batch(rows, source_lang: str, polite_delay: float, user_agent: str):
    """
    Fetch page content for each row, and the source-language equivalent
    where applicable. Returns a dict mapping language → list of page
    records.
    """
    by_lang = {}
    source_cache = {}

    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for row in rows:
        url = row["url"]
        lang = row["language"]
        canonical = row.get("canonical_url") or url

        print(f"Fetching: {url} ({lang})", file=sys.stderr)
        try:
            html, status, final_url = fetch_html(url, user_agent=user_agent)
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            status = 0
            final_url = url
            html = None

        record = {
            "url": url,
            "final_url": final_url,
            "status": status,
            "language": lang,
            "canonical_url": canonical,
            "fetched_at": fetched_at,
            "title": "",
            "meta_description": "",
            "h1": "",
            "lang_attr": "",
            "body_text": "",
            "source_pair": None,
        }

        if html:
            record.update(extract_fields(html))

        # Fetch the source-language equivalent if this isn't already
        # the source language, and cache it so repeated canonical refs
        # don't refetch.
        if lang != source_lang and canonical and canonical != url:
            if canonical not in source_cache:
                print(f"  Fetching source pair: {canonical}", file=sys.stderr)
                try:
                    src_html, src_status, src_final = fetch_html(canonical, user_agent=user_agent)
                except Exception as exc:
                    print(f"    ERROR fetching source: {exc}", file=sys.stderr)
                    src_html, src_status, src_final = None, 0, canonical
                if src_html:
                    src_fields = extract_fields(src_html)
                    source_cache[canonical] = {
                        "url": canonical,
                        "final_url": src_final,
                        "status": src_status,
                        **src_fields,
                    }
                else:
                    source_cache[canonical] = {
                        "url": canonical,
                        "final_url": src_final,
                        "status": src_status,
                        "title": "",
                        "meta_description": "",
                        "h1": "",
                        "lang_attr": "",
                        "body_text": "",
                    }
                time.sleep(polite_delay)
            record["source_pair"] = source_cache[canonical]

        by_lang.setdefault(lang, []).append(record)
        time.sleep(polite_delay)

    return by_lang


def read_from_csv_to_records(rows, source_lang: str):
    """Convert externally-supplied CSV rows into the page-record shape."""
    by_lang = {}
    source_cache = {}

    # First pass: index source-language rows by URL so we can pair them.
    for row in rows:
        if row.get("language") == source_lang:
            source_cache[row.get("url", "")] = {
                "url": row.get("url", ""),
                "final_url": row.get("final_url", row.get("url", "")),
                "status": int(row.get("status", "200") or "200"),
                "title": row.get("title", ""),
                "meta_description": row.get("meta_description", ""),
                "h1": row.get("h1", ""),
                "lang_attr": row.get("lang_attr", ""),
                "body_text": row.get("body_text", ""),
            }

    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for row in rows:
        lang = row.get("language", "unknown")
        url = row.get("url", "")
        canonical = row.get("canonical_url", url) or url

        record = {
            "url": url,
            "final_url": row.get("final_url", url),
            "status": int(row.get("status", "200") or "200"),
            "language": lang,
            "canonical_url": canonical,
            "fetched_at": fetched_at,
            "title": row.get("title", ""),
            "meta_description": row.get("meta_description", ""),
            "h1": row.get("h1", ""),
            "lang_attr": row.get("lang_attr", ""),
            "body_text": row.get("body_text", ""),
            "source_pair": source_cache.get(canonical) if lang != source_lang else None,
        }
        by_lang.setdefault(lang, []).append(record)

    return by_lang


def write_outputs(by_lang: dict, project_dir: Path, batch_number: int):
    """Write one JSON file per language."""
    data_dir = project_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for lang, records in by_lang.items():
        path = data_dir / f"pages-{lang}-batch-{batch_number:02d}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        print(f"Wrote {len(records)} page records to {path}", file=sys.stderr)


def next_batch_number(project_dir: Path) -> int:
    """Find the next available batch number by scanning existing data files."""
    data_dir = project_dir / "data"
    if not data_dir.exists():
        return 1
    pattern = re.compile(r"pages-[^-]+-batch-(\d+)\.json$")
    existing = [
        int(pattern.search(p.name).group(1))
        for p in data_dir.glob("pages-*-batch-*.json")
        if pattern.search(p.name)
    ]
    return (max(existing) + 1) if existing else 1


def main():
    parser = argparse.ArgumentParser(description="Fetch live page content for the next batch of audit URLs.")
    parser.add_argument("--project-dir", default=".",
                        help="Path to the audit project folder.")
    parser.add_argument("--batch-size", type=int, default=20,
                        help="How many URLs to take from the top of open.csv (default 20).")
    parser.add_argument("--source-lang", required=True,
                        help="Source language code (e.g., 'en').")
    parser.add_argument("--from-csv", default=None,
                        help="Path to a pre-extracted CSV (e.g., Screaming Frog export). When set, "
                             "no HTTP fetches are made; the CSV's rows are converted into the standard "
                             "page-record shape.")
    parser.add_argument("--polite-delay", type=float, default=1.0,
                        help="Seconds to wait between page fetches (default 1.0).")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT,
                        help="User-Agent string for page requests.")
    parser.add_argument("--batch-number", type=int, default=None,
                        help="Override the auto-detected batch number.")
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    batch_number = args.batch_number or next_batch_number(project_dir)

    if args.from_csv:
        rows = read_from_csv_input(Path(args.from_csv))
        by_lang = read_from_csv_to_records(rows, args.source_lang)
    else:
        open_csv = project_dir / "urls" / "open.csv"
        if not open_csv.exists():
            print(f"ERROR: {open_csv} not found. Run fetch_sitemap.py first.", file=sys.stderr)
            sys.exit(1)
        all_rows = read_open_csv(open_csv)
        batch_rows = all_rows[:args.batch_size]
        if not batch_rows:
            print("open.csv is empty — nothing to fetch.", file=sys.stderr)
            sys.exit(0)
        print(f"Processing batch {batch_number}: {len(batch_rows)} URLs", file=sys.stderr)
        by_lang = fetch_batch(
            rows=batch_rows,
            source_lang=args.source_lang,
            polite_delay=args.polite_delay,
            user_agent=args.user_agent,
        )

    write_outputs(by_lang, project_dir, batch_number)
    print(f"\nBatch {batch_number} fetched. Next step: run the audit phase.", file=sys.stderr)
    print(f"(URLs are NOT yet moved out of open.csv — that happens after the audit doc is built.)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
