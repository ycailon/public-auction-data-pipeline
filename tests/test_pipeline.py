import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from auction_pipeline.pipeline import AuctionCardParser, PipelineError, normalize, parse_date, parse_eu_decimal, run

ROOT = Path(__file__).resolve().parents[1]


class TestAuctionPipeline(unittest.TestCase):
    def test_multinational_numbers(self):
        self.assertEqual("1250000.00", parse_eu_decimal("1.250.000,00"))
        self.assertEqual("1250000.00", parse_eu_decimal("1,250,000.00"))
        self.assertEqual("82.50", parse_eu_decimal("82,50"))
        self.assertEqual("145000.50", parse_eu_decimal("145 000,50"))

    def test_rejects_malformed_numbers(self):
        for bad in (-5, "abc", "", None, True):
            with self.subTest(bad=bad), self.assertRaises(PipelineError):
                parse_eu_decimal(bad)

    def test_supported_dates(self):
        self.assertEqual("2026-11-20", parse_date("20.11.2026"))
        self.assertEqual("2026-12-18", parse_date("18/12/2026"))

    def test_html_card_parser(self):
        parser = AuctionCardParser()
        parser.feed('<article class="auction-card" data-country="HR" data-title="test"></article>')
        self.assertEqual([{"country": "HR", "title": "test"}], parser.records)

    def test_pipeline_produces_provenance_and_conflict(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            summary = run(ROOT / "fixtures/sources.json", output)
            self.assertEqual({"source_rows": 7, "canonical_properties": 5, "rejected_rows": 1, "conflicts": 1, "rag_chunks": 5}, summary)
            with (output / "normalized.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(5, len(rows))
            self.assertTrue(all(x["source_name"] and x["source_url"] and x["source_record_id"] for x in rows))
            hr = next(x for x in rows if x["cadastre_id"] == "HR-7788")
            self.assertEqual("127500.00", hr["price_eur"])
            self.assertEqual("example_partner_feed", hr["source_name"])
            conflicts = [json.loads(line) for line in (output / "conflicts.jsonl").read_text().splitlines()]
            self.assertEqual("price_eur", next(iter(conflicts[0]["differences"])))
            db = sqlite3.connect(output / "auctions.sqlite")
            self.assertEqual(5, db.execute("SELECT COUNT(*) FROM auctions").fetchone()[0])
            db.close()

    def test_rerunning_is_snapshot_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            run(ROOT / "fixtures/sources.json", folder)
            before = (Path(folder) / "normalized.csv").read_bytes()
            run(ROOT / "fixtures/sources.json", folder)
            self.assertEqual(before, (Path(folder) / "normalized.csv").read_bytes())

    def test_directory_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "sources.json").write_text(json.dumps({"sources": [{"file": "../../../../etc/passwd", "kind": "csv", "name": "bad"}]}))
            with self.assertRaisesRegex(PipelineError, "escapes"):
                run(base / "sources.json", base / "out")

    def test_rejects_unapproved_source_host(self):
        source = {"name": "fake", "source_url": "https://not-example.com/", "observed_at": "2026-10-10T00:00:00Z"}
        record = {"country": "FR", "cadastre_id": "FR-123", "source_record_id": "X", "title": "Apartment",
                  "auction_date": "2026-11-20", "price_eur": "50000", "area_sqm": "50", "language": "fr"}
        with self.assertRaisesRegex(PipelineError, "example domain"):
            normalize(record, source)


if __name__ == "__main__":
    unittest.main()
