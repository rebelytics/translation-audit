#!/usr/bin/env python3
"""
build_mapping.py — Phase 2 fallback: build the source->target URL mapping
from on-page hreflang when the sitemap carries none.

Use this when `fetch_sitemap.py` returns 0 rows because the site keeps
each language on its own domain/ccTLD (or subfolder) and the sitemaps
have no `<xhtml:link rel="alternate" hreflang>` annotations — the common
PrestaShop / Magento international setup. In that topology the
source-language and target-language pages live on different hosts and the
only thing that pairs them is the per-page hreflang block.

Strategy: anchor on the SOURCE-language pages, fetch each one, read its
`<link rel="alternate" hreflang>` set, and pair it with the target-
language equivalents. Writes the two artefacts Phase 4 expects:

  <project>/data/url-mapping.json   canonical(source) -> {lang -> url}
  <project>/urls/open.csv           one row per (source x target) pair,
                                    schema: url, language, canonical_url,
                                    page_type, priority_score, notes

Source pages come from any of (combine freely):
  --source-sitemap URL     a <urlset> sitemap of source-language pages
  --source-url URL         an explicit source page (repeatable)
  --source-urls-csv PATH   a CSV with a 'url' column

Regional target variants (e.g. nl-NL vs nl-BE) are kept distinct: when a
target base code has several regional alternates, the home-region variant
(nl -> nl-NL) is chosen by default, overridable with --prefer-region, and
the collision is always reported so nothing is picked silently.

Usage:
  python build_mapping.py --project-dir ./my-audit \\
      --source-lang en --target-langs de,fr,es,it,nl \\
      --source-sitemap https://example.com/sitemapEN.xml

Run with --help for full options.
"""

import argparse
import csv
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
DEFAULT_USER_AGENT = "translation-audit/1.0 (+https://github.com/rebelytics/translation-audit)"
OPEN_CSV_FIELDS = ["url", "language", "canonical_url", "page_type", "priority_score", "notes"]


def fetch(url: str, timeout: int = 30, user_agent: str = DEFAULT_USER_AGENT):
    """Fetch a URL. Returns (text, status_code, final_url); text is None on
    a non-200 response or a transport error."""
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xml"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001 — surface transport errors to the caller
        print(f"  ERROR fetching {url}: {exc}", file=sys.stderr)
        return None, 0, url
    if r.status_code != 200:
        return None, r.status_code, r.url
    return r.text, r.status_code, r.url


def source_urls_from_sitemap(text: str):
    """Yield <loc> URLs from a <urlset> sitemap (source-language pages)."""
    root = ET.fromstring(text.lstrip().encode("utf-8") if isinstance(text, str) else text)
    if root.tag != f"{SITEMAP_NS}urlset":
        print("  WARNING: --source-sitemap is not a <urlset>; expected a flat "
              "sitemap of source-language pages. Skipping.", file=sys.stderr)
        return
    for url_el in root.findall(f"{SITEMAP_NS}url"):
        loc = url_el.find(f"{SITEMAP_NS}loc")
        if loc is not None and loc.text:
            yield loc.text.strip()


def read_urls_csv(path: Path):
    """Read source URLs from a CSV with a 'url' column (case-insensitive)."""
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = {c.lower(): c for c in (reader.fieldnames or [])}
        if "url" not in cols:
            print(f"  WARNING: {path} has no 'url' column; ignoring.", file=sys.stderr)
            return
        for row in reader:
            value = (row.get(cols["url"]) or "").strip()
            if value:
                yield value


def hreflang_alternates(html: str) -> dict:
    """Return {hreflang_lower: href} for every <link rel=alternate hreflang>."""
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for link in soup.find_all("link", rel="alternate"):
        hl, href = link.get("hreflang"), link.get("href")
        if hl and href:
            out[hl.strip().lower()] = href.strip()
    return out


def base_code(hreflang: str) -> str:
    return hreflang.split("-")[0]


def resolve_target(code: str, alternates: dict, prefer_region: dict):
    """Pick the target URL for base language `code` from a page's alternates.

    Returns (url, matched_hreflang, collision_note). url is None when the
    page has no alternate for this language. collision_note is set only
    when more than one regional variant existed and one had to be chosen.
    """
    cands = [(hl, href) for hl, href in alternates.items()
             if hl != "x-default" and base_code(hl) == code]
    if not cands:
        return None, None, None
    if len(cands) == 1:
        return cands[0][1], cands[0][0], None

    # Multiple regional variants for the same base code (e.g. nl-NL, nl-BE).
    bare = [(hl, href) for hl, href in cands if "-" not in hl]
    by_region = {hl.split("-")[1].upper(): (hl, href) for hl, href in cands if "-" in hl}

    pr = (prefer_region.get(code) or "").upper()
    if pr and pr in by_region:
        hl, href = by_region[pr]
        why = f"--prefer-region {code}={pr}"
    elif code.upper() in by_region:           # home-region heuristic: nl -> nl-NL
        hl, href = by_region[code.upper()]
        why = f"home region {hl}"
    elif bare:
        hl, href = bare[0]
        why = f"bare base code {hl}"
    else:
        hl, href = sorted(cands)[0]
        why = f"first of {sorted(h for h, _ in cands)} (ambiguous)"
    note = (f"{code}: chose {hl} from "
            f"{sorted(h for h, _ in cands)} ({why})")
    return href, hl, note


def build(source_urls, source_lang, target_langs, prefer_region,
          polite_delay, user_agent):
    """Fetch each source page, pair with target alternates. Returns
    (rows, mapping, stats)."""
    rows, mapping = [], {}
    seen_targets = set()
    stats = {"sources_ok": 0, "sources_failed": 0,
             "missing": [], "collisions": []}

    for i, src in enumerate(source_urls, 1):
        print(f"[{i}/{len(source_urls)}] source: {src}", file=sys.stderr)
        html, status, _ = fetch(src, user_agent=user_agent)
        if not html:
            stats["sources_failed"] += 1
            print(f"  skipped (status {status})", file=sys.stderr)
            continue
        alts = hreflang_alternates(html)
        if not alts:
            stats["sources_failed"] += 1
            print("  no hreflang on this page — cannot pair, skipping", file=sys.stderr)
            continue
        stats["sources_ok"] += 1

        entry = {source_lang: src}
        for code in target_langs:
            url, _hl, note = resolve_target(code, alts, prefer_region)
            if note:
                stats["collisions"].append(f"{src} -> {note}")
            if not url:
                stats["missing"].append(f"{src} (missing {code})")
                continue
            entry[code] = url
            if url in seen_targets:
                continue
            seen_targets.add(url)
            rows.append({
                "url": url,
                "language": code,
                "canonical_url": src,
                "page_type": "",
                "priority_score": "",
                "notes": "",
            })
        mapping[src] = entry
        time.sleep(polite_delay)

    return rows, mapping, stats


def write_open_csv(rows, path: Path, append: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    mode = "a" if (append and exists) else "w"
    with open(path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OPEN_CSV_FIELDS)
        if mode == "w" or not exists:
            writer.writeheader()
        writer.writerows(rows)


def parse_prefer_region(value: str) -> dict:
    """Parse 'nl=NL,pt=BR' into {'nl': 'NL', 'pt': 'BR'}."""
    out = {}
    for part in (value or "").split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip().lower()] = v.strip()
    return out


def main():
    p = argparse.ArgumentParser(
        description="Build source->target URL mapping from on-page hreflang "
                    "(Phase 2 fallback when the sitemap has no hreflang).")
    p.add_argument("--project-dir", default=".", help="Audit project folder.")
    p.add_argument("--source-lang", required=True, help="Source language code (e.g. 'en').")
    p.add_argument("--target-langs", required=True,
                   help="Comma-separated target base codes (e.g. 'de,fr,es,it,nl').")
    p.add_argument("--source-sitemap", action="append", default=[],
                   help="A <urlset> sitemap of source-language pages (repeatable).")
    p.add_argument("--source-url", action="append", default=[],
                   help="An explicit source page URL (repeatable).")
    p.add_argument("--source-urls-csv", default=None,
                   help="CSV with a 'url' column listing source pages.")
    p.add_argument("--prefer-region", default="",
                   help="Disambiguate regional collisions, e.g. 'nl=NL,pt=BR'. "
                        "Default: the home-region variant (nl -> nl-NL).")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap the number of source pages processed.")
    p.add_argument("--append", action="store_true",
                   help="Append to an existing open.csv instead of overwriting.")
    p.add_argument("--polite-delay", type=float, default=1.0,
                   help="Seconds between page fetches (default 1.0).")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent string.")
    args = p.parse_args()

    target_langs = [c.strip().lower() for c in args.target_langs.split(",") if c.strip()]
    prefer_region = parse_prefer_region(args.prefer_region)
    user_agent = args.user_agent

    # Gather source URLs from all provided inputs, de-duplicated, order-preserving.
    source_urls, seen = [], set()

    def add(u):
        if u and u not in seen:
            seen.add(u)
            source_urls.append(u)

    for sm in args.source_sitemap:
        print(f"Fetching source sitemap: {sm}", file=sys.stderr)
        text, status, _ = fetch(sm, user_agent=user_agent)
        if not text:
            print(f"  WARNING: could not fetch {sm} (status {status})", file=sys.stderr)
            continue
        for u in source_urls_from_sitemap(text):
            add(u)
    for u in args.source_url:
        add(u)
    if args.source_urls_csv:
        for u in read_urls_csv(Path(args.source_urls_csv)):
            add(u)

    if not source_urls:
        print("ERROR: no source URLs. Provide --source-sitemap, --source-url, "
              "or --source-urls-csv.", file=sys.stderr)
        sys.exit(1)

    if args.limit is not None:
        source_urls = source_urls[:args.limit]

    print(f"Processing {len(source_urls)} source page(s) -> "
          f"targets {target_langs}\n", file=sys.stderr)

    rows, mapping, stats = build(
        source_urls, args.source_lang, target_langs, prefer_region,
        args.polite_delay, user_agent,
    )

    project_dir = Path(args.project_dir)
    open_csv = project_dir / "urls" / "open.csv"
    mapping_path = project_dir / "data" / "url-mapping.json"
    write_open_csv(rows, open_csv, args.append)
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    # Summary.
    print(f"\nSource pages OK: {stats['sources_ok']}  "
          f"failed/unpaired: {stats['sources_failed']}", file=sys.stderr)
    print(f"Wrote {len(rows)} target row(s) "
          f"({'appended to' if args.append else 'to'} {open_csv})", file=sys.stderr)
    print(f"Wrote mapping for {len(mapping)} source page(s) to {mapping_path}", file=sys.stderr)
    per_lang = {c: sum(1 for r in rows if r["language"] == c) for c in target_langs}
    print(f"Per-language rows: {per_lang}", file=sys.stderr)
    if stats["collisions"]:
        print(f"\nRegional collisions resolved ({len(stats['collisions'])}) — review "
              "if a different regional variant was intended:", file=sys.stderr)
        for c in stats["collisions"][:20]:
            print(f"  {c}", file=sys.stderr)
        if len(stats["collisions"]) > 20:
            print(f"  … and {len(stats['collisions']) - 20} more", file=sys.stderr)
    if stats["missing"]:
        print(f"\nMissing target alternates ({len(stats['missing'])}) — pages with no "
              "equivalent in some target language:", file=sys.stderr)
        for m in stats["missing"][:20]:
            print(f"  {m}", file=sys.stderr)
        if len(stats["missing"]) > 20:
            print(f"  … and {len(stats['missing']) - 20} more", file=sys.stderr)


if __name__ == "__main__":
    main()
