from datetime import date

from openpyxl import load_workbook

from tariff_pipeline.config import load_layout
from tariff_pipeline.generate import generate


def test_generation_is_deterministic(tmp_path):
    a = generate(tmp_path / "a", date(2026, 1, 1), 2, seed=1, defect_rate=0.1)
    b = generate(tmp_path / "b", date(2026, 1, 1), 2, seed=1, defect_rate=0.1)
    assert a["workbooks"] == b["workbooks"]
    assert a["injected_defects"] == b["injected_defects"]


def test_workbook_matches_layout_contract(pipeline_dirs):
    layout = load_layout()
    first = min(pipeline_dirs["landing"].glob("*.xlsx"))
    wb = load_workbook(first, read_only=True)
    assert layout["metadata_sheet"]["name"] in wb.sheetnames
    for spec in layout["sheets"].values():
        ws = wb[spec["sheet_name"]]
        header = next(ws.iter_rows(min_row=spec["header_row"], max_row=spec["header_row"],
                                   values_only=True))
        assert list(spec["columns"]) == [h for h in header if h is not None]


def test_only_synthetic_identifiers(pipeline_dirs):
    for name in pipeline_dirs["manifest"]["workbooks"]:
        assert name.startswith("bitacora_") and "REQ-" in name
