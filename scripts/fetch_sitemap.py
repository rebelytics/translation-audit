#!/usr/bin/env python3
"""
fetch_sitemap.py — discover URLs from one or more XML sitemaps.

Handles three common sitemap shapes:
  1. Single <urlset> sitemap (all URLs in one file)
  2. <sitemapindex> pointing to per-section or per-language sitemaps
     (followed recursively, one level deep by default)
  3. Sitemap with hreflang annotations (<xhtml:link rel="alternate"
     hreflang="..."> siblings on each <url> entry)

Writes results to <project_dir>/urls/open.csv with the schema:
  url, language, canonical_url, page_type, priority_score, notes

Also writes <project_dir>/data/url-mapping.json mapping canonical URLs
to their language alternates (only when hreflang is present).

Phase 2 rules applied:
  - Source-language URLs are comparison references, not audit targets.
    They are written into url-mapping.json but excluded from open.csv
    by default. Use --include-source to opt in.
  - When multiple regional variants resolve to the same base language
    code (e.g. nl-NL vs nl-BE for target 'nl'), they are kept distinct
    in url-mapping.json by their full hreflang code; for the audit
    queue, one variant is chosen by the home-region heuristic and the
    collision is reported. Use --prefer-region to override.
  - For the source side, when multiple regional variants exist for the
    source language (e.g. en, en-GB, en-US), the canonical source URL
    is chosen in priority order: sitemap <loc> match → x-default →
    bare base code → region-suffixed.

For sites where each language lives on its own ccTLD/domain and the
per-shop sitemaps carry no hreflang, fetch_sitemap.py will discover
nothing useful — use the companion build_mapping.py instead, which
walks source pages and reads on-page hreflang.

Usage:
  python fetch_sitemap.py --sitemap https://example.com/sitemap.xml \\
      --project-dir ./my-audit \\
      --source-lang en \\
      --target-langs de,fr,es

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


SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
XHTML_NS = "{http://www.w3.org/1999/xhtml}"
DEFAULT_USER_AGENT = "translation-audit/1.0 (+https://github.com/rebelytics/translation-audit)"


def fetch_xml(url: str, timeout: int = 30, user_agent: str = DEFAULT_USER_AGENT) -> ET.Element:
    """Fetch a URL and return the parsed XML root element."""
    headers = {"User-Agent": user_agent, "Accept": "application/xml,text/xml"}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    content = response.content.lstrip()
    return ET.fromstring(content)


def is_sitemap_index(root: ET.Element) -> bool:
    return root.tag == f"{SITEMAP_NS}sitemapindex"


def is_urlset(root: ET.Element) -> bool:
    return root.tag == f"{SITEMAP_NS}urlset"


def parse_urlset(root: ET.Element):
    """
    Yield (url, hreflang_alternates) tuples from a <urlset>.

    hreflang_alternates is a dict mapping hreflang code → URL, or empty
    if no annotations are present. Keys preserve the full hreflang
    (e.g. 'nl-BE') so the caller can distinguish regional variants.
    """
    for url_el in root.findall(f"{SITEMAP_NS}url"):
        loc_el = url_el.find(f"{SITEMAP_NS}loc")
        if loc_el is None or not loc_el.text:
            continue
        url = loc_el.text.strip()
        alternates = {}
        for link_el in url_el.findall(f"{XHTML_NS}link"):
            hreflang = link_el.get("hreflang")
            href = link_el.get("href")
            if hreflang and href:
                alternates[hreflang.strip().lower()] = href.strip()
        yield url, alternates


def parse_sitemap_index(root: ET.Element):
    """Yield child sitemap URLs from a <sitemapindex>."""
    for sm_el in root.findall(f"{SITEMAP_NS}sitemap"):
        loc_el = sm_el.find(f"{SITEMAP_NS}loc")
        if loc_el is not None and loc_el.text:
            yield loc_el.text.strip()


def detect_language_from_url(url: str, language_codes: list) -> str:
    """
    Guess the language of a URL from its path or domain.

    Strategy (in order):
      1. First path segment matches a known language code (e.g., /de/...)
      2. ccTLD matches a known code (e.g., .de → de)
      3. Subdomain matches (e.g., de.example.com → de)
    Returns the matched code or "unknown".
    """
    parsed = urlparse(url)

    path_parts = [p for p in parsed.path.split("/") if p]
    if path_parts and path_parts[0].lower() in language_codes:
        return path_parts[0].lower()

    host_parts = parsed.hostname.split(".") if parsed.hostname else []
    if host_parts and host_parts[-1].lower() in language_codes:
        return host_parts[-1].lower()

    if len(host_parts) > 2 and host_parts[0].lower() in language_codes:
        return host_parts[0].lower()

    return "unknown"


def base_code(hreflang: str) -> str:
    """Reduce a hreflang to its base language code (everything before the
    first '-'). 'x-default' is preserved as-is."""
    if hreflang == "x-default":
        return hreflang
    return hreflang.split("-")[0].lower()


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


def resolve_target_for_code(code: str, alternates: dict, prefer_region: dict):
    """
    Pick one URL for base language `code` from a page's alternates.

    Returns (url, matched_hreflang, collision_note). The collision_note
    is set only when multiple regional variants existed for this base
    code; it explains which one was chosen and why.
    """
    cands = [(hl, href) for hl, href in alternates.items()
             if hl != "x-default" and base_code(hl) == code]
    if not cands:
        return None, None, None
    if len(cands) == 1:
        return cands[0][1], cands[0][0], None

    # Multiple regional variants for the same base code.
    bare = [(hl, href) for hl, href in cands if "-" not in hl]
    by_region = {hl.split("-")[1].upper(): (hl, href) for hl, href in cands if "-" in hl}

    pr = (prefer_region.get(code) or "").upper()
    if pr and pr in by_region:
        hl, href = by_region[pr]
        why = f"--prefer-region {code}={pr}"
    elif code.upper() in by_region:
        # Home-region heuristic: nl → nl-NL, fr → fr-FR, etc.
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


def resolve_source_canonical(loc_url: str, alternates: dict, source_lang: str):
    """
    Pick the canonical source URL for a urlset entry whose <loc> may
    or may not be the source-language page.

    Priority:
      1. The <loc> value, if it's a source-language alternate.
      2. The x-default alternate, if present.
      3. The bare base code source alternate (e.g. 'en').
      4. A region-suffixed source variant.
    Returns (canonical_url, note_or_None).
    """
    # Build a quick lookup of alternates whose base matches source_lang.
    source_alts = {hl: href for hl, href in alternates.items()
                   if base_code(hl) == source_lang}

    # 1. Sitemap <loc> if it's a source-language alternate.
    if loc_url in source_alts.values():
        return loc_url, None

    # 2. x-default.
    if "x-default" in alternates:
        return alternates["x-default"], None

    # 3. Bare base code.
    if source_lang in source_alts:
        return source_alts[source_lang], None

    # 4. Any region-suffixed source variant.
    if source_alts:
        hl, href = sorted(source_alts.items())[0]
        return href, f"source canonical fallback: chose {hl} from {sorted(source_alts)}"

    # 5. No source alternate at all. Fall back to the loc URL itself.
    return loc_url, None


def discover(
    sitemap_urls: list,
    source_lang: str,
    target_langs: list,
    prefer_region: dict,
    include_source: bool,
    max_depth: int = 1,
    polite_delay_seconds: float = 0.5,
    user_agent: str = DEFAULT_USER_AGENT,
):
    """
    Walk one or more sitemaps and collect all URLs.

    Returns a tuple (rows, url_mapping, collisions):
      rows is a list of dicts ready to write to open.csv
      url_mapping is a dict canonical_url → {hreflang → url} (may be empty)
      collisions is a list of human-readable collision notes
    """
    seen_targets = set()
    rows = []
    url_mapping = {}
    collisions = []
    sources_added = set()

    worklist = [(url, 0) for url in sitemap_urls]

    while worklist:
        sm_url, depth = worklist.pop(0)
        print(f"Fetching sitemap: {sm_url} (depth {depth})", file=sys.stderr)

        try:
            root = fetch_xml(sm_url, user_agent=user_agent)
        except Exception as exc:
            print(f"  WARNING: could not fetch {sm_url}: {exc}", file=sys.stderr)
            continue

        if is_sitemap_index(root):
            if depth >= max_depth:
                print(f"  Reached max depth ({max_depth}); not following index.", file=sys.stderr)
                continue
            children = list(parse_sitemap_index(root))
            print(f"  Index found, {len(children)} child sitemaps", file=sys.stderr)
            for child in children:
                worklist.append((child, depth + 1))
            time.sleep(polite_delay_seconds)
            continue

        if not is_urlset(root):
            print(f"  WARNING: root element is neither urlset nor sitemapindex; skipping.", file=sys.stderr)
            continue

        count_added = 0
        for url, alternates in parse_urlset(root):
            if alternates:
                # Pick canonical source URL using the source-pairing priority.
                canonical, src_note = resolve_source_canonical(url, alternates, source_lang)
                if src_note:
                    collisions.append(src_note)

                # Store the full alternates dict (regional variants intact)
                # in the mapping. The mapping is the source of truth for
                # downstream tooling; open.csv is a flat audit queue.
                if canonical not in url_mapping:
                    url_mapping[canonical] = alternates

                # Optionally enqueue the canonical source URL itself for
                # self-audit (typos, broken links) — opt-in only.
                if include_source and canonical not in sources_added:
                    rows.append({
                        "url": canonical,
                        "language": source_lang,
                        "canonical_url": canonical,
                        "page_type": "",
                        "priority_score": "",
                        "notes": "",
                    })
                    sources_added.add(canonical)
                    count_added += 1

                # For each target language, pick one URL (handling
                # regional collisions) and emit a row.
                for code in target_langs:
                    if base_code(code) == source_lang and not include_source:
                        # The target list shouldn't include the source
                        # language unless include_source is set.
                        continue
                    href, _hl, coll_note = resolve_target_for_code(code, alternates, prefer_region)
                    if coll_note:
                        collisions.append(f"{canonical} → {coll_note}")
                    if not href:
                        continue
                    if href in seen_targets:
                        continue
                    seen_targets.add(href)
                    rows.append({
                        "url": href,
                        "language": code,
                        "canonical_url": canonical,
                        "page_type": "",
                        "priority_score": "",
                        "notes": "",
                    })
                    count_added += 1
            else:
                # No hreflang on this <url>. Guess the language from the URL
                # itself. The mapping cannot be built here; the agent will
                # need build_mapping.py to fill it in.
                all_codes = set([source_lang] + list(target_langs))
                lang = detect_language_from_url(url, list(all_codes))
                if lang == "unknown":
                    continue
                if lang == source_lang and not include_source:
                    continue
                if url in seen_targets:
                    continue
                seen_targets.add(url)
                rows.append({
                    "url": url,
                    "language": lang,
                    "canonical_url": url,
                    "page_type": "",
                    "priority_score": "",
                    "notes": "",
                })
                count_added += 1

        print(f"  Added {count_added} URLs from this sitemap", file=sys.stderr)
        time.sleep(polite_delay_seconds)

    return rows, url_mapping, collisions


def write_csv(rows: list, output_path: Path):
    fieldnames = ["url", "language", "canonical_url", "page_type", "priority_score", "notes"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Discover URLs from XML sitemaps for a translation audit.")
    parser.add_argument("--sitemap", required=True, action="append",
                        help="Sitemap URL. Pass multiple times for multiple sitemaps.")
    parser.add_argument("--project-dir", default=".",
                        help="Path to the audit project folder.")
    parser.add_argument("--source-lang", required=True,
                        help="Source language code (e.g., 'en').")
    parser.add_argument("--target-langs", required=True,
                        help="Comma-separated target language codes (e.g., 'de,fr,es').")
    parser.add_argument("--prefer-region", default="",
                        help="Disambiguate regional collisions, e.g. 'nl=NL,pt=BR'. "
                             "Default: the home-region variant (nl → nl-NL).")
    parser.add_argument("--include-source", action="store_true",
                        help="Include source-language URLs in open.csv as audit targets. "
                             "Off by default — source pages are comparison references, not "
                             "targets; opt in only when self-auditing the source language.")
    parser.add_argument("--max-depth", type=int, default=1,
                        help="How many levels of sitemap index to follow (default 1).")
    parser.add_argument("--polite-delay", type=float, default=0.5,
                        help="Seconds to wait between sitemap fetches (default 0.5).")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT,
                        help="User-Agent string for sitemap requests.")
    args = parser.parse_args()

    target_langs = [c.strip().lower() for c in args.target_langs.split(",") if c.strip()]
    prefer_region = parse_prefer_region(args.prefer_region)

    rows, url_mapping, collisions = discover(
        sitemap_urls=args.sitemap,
        source_lang=args.source_lang.lower(),
        target_langs=target_langs,
        prefer_region=prefer_region,
        include_source=args.include_source,
        max_depth=args.max_depth,
        polite_delay_seconds=args.polite_delay,
        user_agent=args.user_agent,
    )

    project_dir = Path(args.project_dir)
    open_csv = project_dir / "urls" / "open.csv"
    write_csv(rows, open_csv)
    print(f"\nWrote {len(rows)} URLs to {open_csv}", file=sys.stderr)

    if url_mapping:
        mapping_path = project_dir / "data" / "url-mapping.json"
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(url_mapping, f, indent=2, ensure_ascii=False)
        print(f"Wrote URL mapping ({len(url_mapping)} canonical URLs) to {mapping_path}", file=sys.stderr)
    else:
        print("No hreflang annotations in the sitemap(s) — URL mapping not written.",
              file=sys.stderr)
        print("If the site uses per-domain ccTLDs without sitemap hreflang, run "
              "build_mapping.py instead.", file=sys.stderr)

    if collisions:
        print(f"\nRegional / source-pairing notes ({len(collisions)}) — review if a "
              "different variant was intended:", file=sys.stderr)
        for c in collisions[:20]:
            print(f"  {c}", file=sys.stderr)
        if len(collisions) > 20:
            print(f"  … and {len(collisions) - 20} more", file=sys.stderr)


if __name__ == "__main__":
    main()
