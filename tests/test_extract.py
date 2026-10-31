import csv


def rows(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_every_workbook_becomes_a_batch(pipeline_dirs):
    s = pipeline_dirs["summary"]
    assert s["files"] == s["batches"] == len(pipeline_dirs["manifest"]["workbooks"])


def test_dates_are_normalised_to_iso(pipeline_dirs):
    for r in rows(pipeline_dirs["staged"] / "tariff_batches.csv"):
        y, m, d = r["effective_date"].split("-")
        assert len(y) == 4 and len(m) == 2 and len(d) == 2


def test_rows_without_billing_code_are_quarantined_not_dropped(pipeline_dirs):
    injected = sum(1 for d in pipeline_dirs["manifest"]["injected_defects"]
                   if d["kind"] == "missing_cbs_code")
    q = [r for r in rows(pipeline_dirs["staged"] / "quarantine.csv") if "cbs_code" in r["reason"]]
    assert len(q) >= injected > 0
    for table in ("prepaid_plans", "postpaid_plans", "b2b_access", "b2b_inbound_access"):
        assert all(r["cbs_code"] for r in rows(pipeline_dirs["staged"] / f"{table}.csv"))


def test_lineage_columns_present(pipeline_dirs):
    r = rows(pipeline_dirs["staged"] / "prepaid_plans.csv")[0]
    assert r["_source_file"].endswith(".xlsx") and int(r["_row_number"]) > 3
    assert r["requirement_id"].startswith("REQ-")
