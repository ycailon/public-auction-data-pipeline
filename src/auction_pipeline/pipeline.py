"""Provenance-preserving normalization for fictional cross-border auction listings.

No network requests. Not a production scraper or legal/property registry verifier.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

COLUMNS = ("record_key", "country", "cadastre_id", "title", "auction_date", "price_eur", "area_sqm", "language", "source_name", "source_record_id", "source_url", "observed_at")


class PipelineError(ValueError):
    pass


class AuctionCardParser(HTMLParser):
    """Read declared `data-*` attributes from a small illustrative card layout."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrib = dict(attrs)
        if tag == "article" and "auction-card" in (attrib.get("class") or "").split():
            self.records.append({key.removeprefix("data-"): val for key, val in attrib.items()
                                 if key.startswith("data-") and isinstance(val, str)})


def _read_source(path: Path, kind: str) -> list[dict[str, Any]]:
    if kind == "csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    if kind == "json":
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, list) or not all(isinstance(x, dict) for x in obj):
            raise PipelineError("JSON input must be a list of objects")
        return obj
    if kind == "html":
        parser = AuctionCardParser()
        parser.feed(path.read_text(encoding="utf-8"))
        return parser.records
    raise PipelineError(f"unsupported source type: {kind}")


def parse_eu_decimal(val: Any) -> str:
    """Accept comma/dot thousands and decimal patterns; return two-decimal string."""
    if isinstance(val, bool) or val is None:
        raise PipelineError("missing numeric value")
    cleaned = re.sub(r"[\s\u00a0€]", "", str(val))
    if not cleaned or not re.fullmatch(r"\d[\d.,]*", cleaned):
        raise PipelineError("invalid numeric value")
    if "," in cleaned and "." in cleaned:
        decimal_char = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        grouping = "." if decimal_char == "," else ","
        cleaned = cleaned.replace(grouping, "").replace(decimal_char, ".")
    elif "," in cleaned:
        if cleaned.count(",") > 1 or len(cleaned.rsplit(",", 1)[1]) == 3:
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(",", ".")
    elif "." in cleaned and (cleaned.count(".") > 1 or len(cleaned.rsplit(".", 1)[1]) == 3):
        cleaned = cleaned.replace(".", "")
    try:
        number = Decimal(cleaned)
    except InvalidOperation as exc:
        raise PipelineError("invalid decimal") from exc
    if not number.is_finite() or number <= 0 or number > 10**12:
        raise PipelineError("amount outside expected range")
    return str(number.quantize(Decimal("0.01")))


def parse_date(val: Any) -> str:
    if not isinstance(val, str):
        raise PipelineError("missing auction date")
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(val.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    raise PipelineError("unrecognized auction date")


def normalize(raw: dict[str, Any], source: dict[str, str]) -> dict[str, str]:
    mapping = source.get("mapping", {})
    if not isinstance(mapping, dict):
        raise PipelineError("mapping must be an object")
    def pick(field):
        return raw.get(mapping.get(field, field))
    country = str(pick("country") or "").upper().strip()
    if country not in {"HR", "DE", "FR", "IT", "AT"}:
        raise PipelineError("unsupported country")
    ident = str(pick("cadastre_id") or "").strip().upper()
    source_id = str(pick("source_record_id") or "").strip()
    title = str(pick("title") or "").strip()
    lang = str(pick("language") or "").lower().strip()
    if not ident or len(ident) > 100 or not re.fullmatch(r"[A-Z0-9-]+", ident):
        raise PipelineError("invalid cadastre reference")
    if not source_id or len(source_id) > 120 or not title or len(title) > 200:
        raise PipelineError("missing source ID or title")
    if lang not in {"hr", "de", "fr", "it", "en"}:
        raise PipelineError("unrecognized language")
    record_key = hashlib.sha256(f"{country}:{ident}".encode()).hexdigest()[:20]
    auction_date = parse_date(pick("auction_date"))
    price = parse_eu_decimal(pick("price_eur"))
    area = parse_eu_decimal(pick("area_sqm"))
    obs = str(source.get("observed_at") or "")
    try:
        observed_at = datetime.fromisoformat(obs.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PipelineError("invalid source observed_at") from exc
    if observed_at.tzinfo is None:
        raise PipelineError("source observed_at needs timezone")
    root = str(source.get("source_url", ""))
    if not root.startswith(("https://example.org/", "https://example.com/")):
        raise PipelineError("demo source URL must be on an example domain")
    return dict(record_key=record_key, country=country, cadastre_id=ident,
                title=title, auction_date=auction_date, price_eur=price,
                area_sqm=area, language=lang, source_name=str(source["name"]),
                source_record_id=source_id, source_url=root, observed_at=observed_at.isoformat())


def run(manifest_path: str | Path, output_dir: str | Path) -> dict[str, int]:
    manifest_path = Path(manifest_path).resolve()
    base = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest.get("sources"), list):
        raise PipelineError("manifest requires list of sources")
    normalized: dict[str, dict[str, str]] = {}
    rejected: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    raw_count = 0
    for source in manifest["sources"]:
        file_name = source["file"]
        # Fixture inputs cannot escape the specified manifest folder.
        path = (base / file_name).resolve()
        if not path.is_relative_to(base):
            raise PipelineError("source path escapes fixture directory")
        records = _read_source(path, source["kind"])
        for index, raw in enumerate(records, start=1):
            raw_count += 1
            try:
                record = normalize(raw, source)
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                rejected.append({"source_name": source.get("name", "unknown"),
                                 "source_row": index, "reason": str(exc)})
                continue
            key = record["record_key"]
            previous = normalized.get(key)
            if previous is not None:
                changed = {col: [previous[col], record[col]] for col in ("price_eur", "auction_date", "area_sqm")
                           if previous[col] != record[col]}
                if changed:
                    conflicts.append({"record_key": key, "previous_source": previous["source_name"],
                                      "incoming_source": record["source_name"], "differences": changed})
                # Only newer observation wins; tie keeps first seen.
                if record["observed_at"] > previous["observed_at"]:
                    normalized[key] = record
            else:
                normalized[key] = record

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "normalized.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(sorted(normalized.values(), key=lambda x: x["record_key"]))
    _jsonl(output / "rejected.jsonl", rejected)
    _jsonl(output / "conflicts.jsonl", conflicts)
    chunks = [{"record_key": r["record_key"], "text": f"{r['title']}. Auction date: {r['auction_date']}. Price: EUR {r['price_eur']}. Area: {r['area_sqm']} sqm.",
               "source_url": r["source_url"], "source_name": r["source_name"], "language": r["language"],
               "verification_status": "synthetic_unverified"} for r in normalized.values()]
    _jsonl(output / "rag_chunks.jsonl", chunks)
    db = sqlite3.connect(output / "auctions.sqlite")
    db.execute("""CREATE TABLE IF NOT EXISTS auctions (
      record_key TEXT PRIMARY KEY, country TEXT, cadastre_id TEXT, title TEXT,
      auction_date TEXT, price_eur TEXT, area_sqm TEXT, language TEXT,
      source_name TEXT, source_record_id TEXT, source_url TEXT, observed_at TEXT)""")
    with db:
        # Replace complete snapshot: a missing listing in a later authoritative crawl
        # should not survive as though it were still in the current snapshot.
        db.execute("DELETE FROM auctions")
        db.executemany("INSERT INTO auctions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(r[col] for col in COLUMNS) for r in normalized.values()])
    db.close()
    summary = {"source_rows": raw_count, "canonical_properties": len(normalized),
               "rejected_rows": len(rejected), "conflicts": len(conflicts), "rag_chunks": len(chunks)}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
