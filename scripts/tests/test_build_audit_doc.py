#!/usr/bin/env python3
"""Offline tests for build_audit_doc.py: cross-page issue_group cards and
the optional overview section.

Run from anywhere (no network, no third-party packages, no bytecode):
  python3 -B -I scripts/tests/test_build_audit_doc.py
"""

import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
sys.path.insert(0, str(SCRIPTS))

import build_audit_doc as bad  # noqa: E402

FIXTURE = HERE / "fixtures" / "cross-page-overview.json"
CSV_NAME = "audit-2026-01-15-batch-03-instances.csv"


def load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class CrossPageCards(unittest.TestCase):
    def issues(self, payload, lang, bucket, cap=None):
        grouped, _ = bad.group_findings(payload["findings"])
        return bad.group_issues(grouped[lang][bucket], payload.get("group_caps"), cap, CSV_NAME)

    def test_capped_group_headline_and_instances(self):
        (issue,) = self.issues(load(), "de", "likely_error")
        self.assertEqual(issue["diagnosis"],
                         "Meta descriptions left in English — 3 instances on 3 pages; "
                         f"2 shown, all in {CSV_NAME}")
        self.assertEqual(len(issue["instances"]), 2)
        self.assertEqual((issue["total"], issue["pages"], issue["cross_page"]), (3, 3, True))

    def test_group_under_cap_is_counted_not_capped(self):
        (issue,) = self.issues(load(), "fr", "likely_error")
        self.assertEqual(issue["diagnosis"], "Meta descriptions left in English — 2 instances on 2 pages")
        self.assertEqual(len(issue["instances"]), 2)

    def test_same_page_group_unchanged(self):
        (issue,) = self.issues(load(), "de", "worth_checking")
        self.assertEqual(issue["diagnosis"], "Brand token repeated in title and H1")
        self.assertFalse(issue["cross_page"])

    def test_title_that_states_its_count_is_not_counted_twice(self):
        payload = load()
        for f in payload["findings"]:
            if f["issue_group"] == "en-meta":
                f["issue_title"] = "Meta descriptions left in English (3 instances)"
        (issue,) = self.issues(payload, "de", "likely_error")
        self.assertEqual(issue["diagnosis"],
                         f"Meta descriptions left in English (3 instances); 2 shown, all in {CSV_NAME}")

    def test_cli_cap_applies_without_group_caps(self):
        payload = load()
        payload.pop("group_caps")
        (issue,) = self.issues(payload, "de", "likely_error", cap=1)
        self.assertEqual(len(issue["instances"]), 1)
        (uncapped,) = self.issues(payload, "de", "likely_error")
        self.assertEqual(len(uncapped["instances"]), 3)
        self.assertNotIn("shown", uncapped["diagnosis"])

    def test_instances_rows_cover_every_cross_page_instance(self):
        rows = bad.cross_page_rows(load())
        self.assertEqual(len(rows), 5)
        self.assertEqual({r["issue_group"] for r in rows}, {"en-meta"})
        self.assertEqual(sorted({r["language"] for r in rows}), ["de", "fr"])
        self.assertTrue(all(r["issue"] == "Meta descriptions left in English" for r in rows))

    def test_no_cross_page_group_no_rows(self):
        payload = load()
        payload["findings"] = [f for f in payload["findings"] if f["issue_group"] == "brand-a"]
        self.assertEqual(bad.cross_page_rows(payload), [])


class Overview(unittest.TestCase):
    def test_overview_tab_first_and_escaped(self):
        out = bad.build_html(load(), None, CSV_NAME)
        self.assertIn('data-lang="overview">Overview</button>', out)
        self.assertLess(out.index('id="panel-overview"'), out.index('id="panel-de"'))
        self.assertIn('class="panel active ov" id="panel-overview"', out)
        self.assertIn('class="panel" id="panel-de"', out)
        self.assertIn("Template fallback &lt;likely&gt;", out)
        self.assertNotIn("<likely>", out)
        self.assertIn("Checkout help pages", out)
        self.assertIn("Is the English legal text deliberate for every market?", out)

    def test_per_language_counts(self):
        rows = bad.overview_counts(load(), ["de", "fr", "it"])
        self.assertEqual(rows[0], {"language": "de", "pages": 4, "likely_error": 3, "worth_checking": 2})
        self.assertEqual(rows[2], {"language": "it", "pages": 1, "likely_error": 0, "worth_checking": 0})

    def test_markdown_overview_section(self):
        md = bad.build_markdown(load(), None, CSV_NAME)
        self.assertLess(md.index("## Overview"), md.index("## German (de)"))
        self.assertIn("| Meta descriptions left in English | de, fr | 5 | Template fallback <likely> |", md)
        self.assertIn("### Open questions for the team", md)

    def test_without_overview_first_language_is_active(self):
        payload = load()
        payload.pop("overview")
        out = bad.build_html(payload)
        self.assertNotIn('data-lang="overview"', out)
        self.assertIn('class="panel active" id="panel-de"', out)
        self.assertNotIn("## Overview", bad.build_markdown(payload))


class Cli(unittest.TestCase):
    def test_cli_writes_doc_and_instances_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, "-B", "-I", str(SCRIPTS / "build_audit_doc.py"),
                 "--findings", str(FIXTURE), "--project-dir", tmp],
                capture_output=True, text=True, check=True)
            out_dir = Path(tmp) / "findings"
            self.assertTrue((out_dir / "audit-2026-01-15-batch-03.html").exists())
            self.assertTrue((out_dir / "audit-2026-01-15-batch-03.md").exists())
            with open(out_dir / CSV_NAME, encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 5)
            self.assertEqual(list(rows[0].keys()), bad.INSTANCE_COLUMNS)
            self.assertIn("5 instances", proc.stderr)

    def test_cli_no_csv_without_cross_page_group(self):
        payload = copy.deepcopy(load())
        payload["findings"] = [f for f in payload["findings"] if f["issue_group"] == "brand-a"]
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.json"
            src.write_text(json.dumps(payload), encoding="utf-8")
            subprocess.run([sys.executable, "-B", "-I", str(SCRIPTS / "build_audit_doc.py"),
                            "--findings", str(src), "--project-dir", tmp],
                           capture_output=True, text=True, check=True)
            self.assertFalse((Path(tmp) / "findings" / CSV_NAME).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
