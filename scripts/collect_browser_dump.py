#!/usr/bin/env python3
"""
collect_browser_dump.py — disk side of the OPFS browser→disk bridge.

When a site bot-blocks scripted HTTP, page content is fetched from
inside a real browser session (see SKILL.md, "Browser-fetch playbook
for bot-blocked multi-domain sites"). In automated browser sessions
the usual transfer channels are silently blocked — blob downloads are
suppressed, clipboard access throws, and localhost POSTs hang on a
Local Network Access permission no automation can answer. The channel
that needs no permission is the Origin Private File System: the
in-page collector writes `MARKER + JSON.stringify(payload)` to an
OPFS file, and the browser stores that content as a plain file inside
the profile directory. This script locates the newest matching file,
verifies the marker, and extracts the JSON payload.

Usage:
  python collect_browser_dump.py --out dump.json
  python collect_browser_dump.py --out dump.json \
      --marker TA-BATCH02-MARKER-7741 --max-age-min 30
  python collect_browser_dump.py --print-js

The in-page side (see --print-js for a fuller template):

  const j = MARKER + JSON.stringify(payload);
  const root = await navigator.storage.getDirectory();
  const fh = await root.getFileHandle('audit-dump.json', {create: true});
  const w = await fh.createWritable();
  await w.write(j); await w.close();

Tip: test the channel with a tiny payload before committing the real
one, and use a unique marker per run so stale dumps can't be picked up.
"""

import argparse
import glob
import json
import os
import sys
import time

DEFAULT_MARKER = "TRANSLATION-AUDIT-DUMP-V1:"

# Chromium-family profile roots that contain a "File System" store.
PROFILE_GLOBS = [
    "~/Library/Application Support/Google/Chrome/*/File System",       # macOS
    "~/Library/Application Support/Chromium/*/File System",
    "~/.config/google-chrome/*/File System",                           # Linux
    "~/.config/chromium/*/File System",
    "~/AppData/Local/Google/Chrome/User Data/*/File System",           # Windows
]

COLLECTOR_JS_TEMPLATE = r"""
// In-page collector template (run via the browser integration's JS tool).
// 1) Fetch pages (same-origin, or cross-origin when sibling domains serve
//    open CORS — probe that first), accumulating in window.__DUMP across
//    calls so no HTML flows through the agent conversation.
// 2) Write the payload to OPFS with the marker prefix:
(async () => {
  const MARKER = '%MARKER%';
  const payload = window.__DUMP;            // {locale: {host, pages: [...]}}
  const j = MARKER + JSON.stringify(payload);
  const root = await navigator.storage.getDirectory();
  const fh = await root.getFileHandle('audit-dump.json', { create: true });
  const w = await fh.createWritable();
  await w.write(j);
  await w.close();
  return 'OPFS written: ' + j.length + ' chars';
})()
"""


def find_dump(marker: bytes, max_age_min: float, min_size: int):
    """Newest profile-store file that starts with `marker`."""
    cutoff = time.time() - max_age_min * 60
    candidates = []
    for pattern in PROFILE_GLOBS:
        for store in glob.glob(os.path.expanduser(pattern)):
            for dirpath, _dirnames, filenames in os.walk(store):
                for name in filenames:
                    path = os.path.join(dirpath, name)
                    try:
                        st = os.stat(path)
                    except OSError:
                        continue
                    if st.st_size < min_size or st.st_mtime < cutoff:
                        continue
                    try:
                        with open(path, "rb") as fh:
                            head = fh.read(len(marker))
                    except OSError:
                        continue
                    if head == marker:
                        candidates.append((st.st_mtime, path))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def main():
    ap = argparse.ArgumentParser(
        description="Locate and extract an OPFS-bridged JSON dump from the "
                    "browser profile directory.")
    ap.add_argument("--marker", default=DEFAULT_MARKER,
                    help=f"Marker prefix the in-page collector wrote "
                         f"(default: {DEFAULT_MARKER!r}).")
    ap.add_argument("--out", help="Path to write the extracted JSON payload.")
    ap.add_argument("--max-age-min", type=float, default=60.0,
                    help="Only consider files modified in the last N minutes "
                         "(default 60).")
    ap.add_argument("--min-size", type=int, default=64,
                    help="Ignore files smaller than this many bytes.")
    ap.add_argument("--print-js", action="store_true",
                    help="Print the in-page collector JS template and exit.")
    args = ap.parse_args()

    if args.print_js:
        print(COLLECTOR_JS_TEMPLATE.replace("%MARKER%", args.marker))
        return 0

    if not args.out:
        ap.error("--out is required unless --print-js is given")

    marker = args.marker.encode("utf-8")
    path = find_dump(marker, args.max_age_min, args.min_size)
    if path is None:
        print("No dump found. Checks: did the in-page OPFS write report "
              "success? Same marker? Within --max-age-min? Browser profile "
              "under one of the known roots?", file=sys.stderr)
        return 1

    with open(path, "rb") as fh:
        data = fh.read()
    payload = data[len(marker):]
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        print(f"Found {path} but payload is not valid JSON: {exc}",
              file=sys.stderr)
        return 1

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(parsed, fh, ensure_ascii=False)
    top = (f"{len(parsed)} top-level keys" if isinstance(parsed, dict)
           else f"{len(parsed)} items" if isinstance(parsed, list) else "scalar")
    print(f"Extracted {len(payload):,} bytes ({top}) from:\n  {path}\n"
          f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
