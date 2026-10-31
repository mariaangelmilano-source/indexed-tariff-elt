"""Extract: price-log workbooks -> typed-as-text staging files.

Replaces the per-sheet Pentaho transformations of the original thesis
(Excel input -> filter rows -> select values -> add constants -> table output)
with one config-driven step:

* every sheet is read from the header row declared in config/sheets.yml;
* all cells are kept as text (types are enforced in dbt, where they are tested);
* the batch "constants" (requirement id, effective date, official FX rate, cut)
  come from the metadata sheet instead of being typed by hand;
* rows missing a required field go to a quarantine file with the reason,
  so nothing disappears silently.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook

from .config import load_layout


def _text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, datetime):
        return value.date().isoformat()
    s = str(value).strip()
    return s or None


def _metadata(wb, layout) -> dict:
    spec = layout["metadata_sheet"]
    ws = wb[spec["name"]]
    pairs = {_text(r[0]): _text(r[1]) for r in ws.iter_rows(min_row=1, max_col=2, values_only=True)
             if r and r[0] is not None}
    meta = {}
    for field, label in spec["fields"].items():
        if label not in pairs or pairs[label] is None:
            raise ValueError(f"metadata field '{label}' missing")
        meta[field] = pairs[label]
    # Logs carry dd/mm/yyyy; normalise to ISO so every warehouse can cast it.
    raw_date = meta["effective_date"]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            meta["effective_date"] = datetime.strptime(raw_date, fmt).date().isoformat()
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"unparseable effective date '{raw_date}'")
    return meta


def extract(landing: Path, staged: Path) -> dict:
    layout = load_layout()
    staged.mkdir(parents=True, exist_ok=True)
    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    tables: dict[str, list[dict]] = {k: [] for k in layout["sheets"]}
    batches: list[dict] = []
    quarantine: list[dict] = []

    files = sorted(p for p in landing.glob("*.xlsx") if not p.name.startswith("~$"))
    for path in files:
        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            meta = _metadata(wb, layout)
        except (KeyError, ValueError) as exc:
            quarantine.append({"table_name": "tariff_batches", "source_file": path.name,
                               "row_number": None, "reason": f"bad metadata: {exc}",
                               "raw_record": None, "_extracted_at": extracted_at})
            continue
        batches.append({**meta, "_source_file": path.name, "_extracted_at": extracted_at})

        for table, spec in layout["sheets"].items():
            if spec["sheet_name"] not in wb.sheetnames:
                quarantine.append({"table_name": table, "source_file": path.name,
                                   "row_number": None, "reason": "sheet missing",
                                   "raw_record": None, "_extracted_at": extracted_at})
                continue
            ws = wb[spec["sheet_name"]]
            rows = ws.iter_rows(min_row=spec["header_row"], values_only=True)
            header = [_text(h) for h in next(rows)]
            missing_cols = [c for c in spec["columns"] if c not in header]
            if missing_cols:
                quarantine.append({"table_name": table, "source_file": path.name,
                                   "row_number": spec["header_row"],
                                   "reason": f"columns missing: {missing_cols}",
                                   "raw_record": None, "_extracted_at": extracted_at})
                continue
            idx = {spec["columns"][h]: header.index(h) for h in spec["columns"]}
            for offset, raw in enumerate(rows, start=spec["header_row"] + 1):
                if raw is None or all(v is None for v in raw):
                    continue  # blank line, same as Pentaho's "remove empty rows"
                rec = {f: _text(raw[i]) if i < len(raw) else None for f, i in idx.items()}
                gaps = [f for f in spec["required"] if not rec.get(f)]
                if gaps:
                    quarantine.append({"table_name": table, "source_file": path.name,
                                       "row_number": offset,
                                       "reason": f"required field(s) empty: {gaps}",
                                       "raw_record": json.dumps(rec, ensure_ascii=False),
                                       "_extracted_at": extracted_at})
                    continue
                rec.update({"requirement_id": meta["requirement_id"], "_source_file": path.name,
                            "_row_number": offset, "_extracted_at": extracted_at})
                tables[table].append(rec)
        wb.close()

    def dump(name: str, records: list[dict], fields: list[str]):
        with open(staged / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(records)

    for table, spec in layout["sheets"].items():
        fields = list(spec["columns"].values()) + ["requirement_id", "_source_file",
                                                   "_row_number", "_extracted_at"]
        dump(table, tables[table], fields)
    dump("tariff_batches", batches,
         list(layout["metadata_sheet"]["fields"]) + ["_source_file", "_extracted_at"])
    dump("quarantine", quarantine,
         ["table_name", "source_file", "row_number", "reason", "raw_record", "_extracted_at"])

    summary = {"files": len(files), "batches": len(batches), "quarantined": len(quarantine),
               **{t: len(r) for t, r in tables.items()}}
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--landing", default="data/landing")
    ap.add_argument("--staged", default="data/staged")
    a = ap.parse_args()
    print(json.dumps(extract(Path(a.landing), Path(a.staged)), indent=2))


if __name__ == "__main__":
    main()
