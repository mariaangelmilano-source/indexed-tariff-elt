"""Full run: generate -> extract -> load (DuckDB) -> dbt build -> checks.

Skipped automatically when duckdb / dbt are not installed.
"""

import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from tariff_pipeline.load import load_duckdb

duckdb = pytest.importorskip("duckdb")
if shutil.which("dbt") is None:
    pytest.skip("dbt CLI not installed", allow_module_level=True) 

DBT_DIR = Path(__file__).resolve().parents[1] / "dbt"


@pytest.fixture(scope="module")
def warehouse(pipeline_dirs):
    db = pipeline_dirs["root"] / "warehouse.duckdb"
    load_duckdb(pipeline_dirs["staged"], str(db))
    env = {**os.environ, "DUCKDB_PATH": str(db), "DBT_TARGET": "duckdb"}
    res = subprocess.run(["dbt", "build", "--profiles-dir", ".", "--target", "duckdb"],
                     cwd=DBT_DIR, env=env, capture_output=True, text=True, check=False)
    assert res.returncode == 0, res.stdout[-4000:] + res.stderr[-2000:]
    con = duckdb.connect(str(db), read_only=True)
    yield con
    con.close()


def test_injected_conversion_errors_are_detected(warehouse, pipeline_dirs):
    injected = Counter(d["kind"] for d in pipeline_dirs["manifest"]["injected_defects"])
    got = dict(warehouse.execute(
        "select alignment_status, count(*) from analytics.fct_fx_alignment group by 1").fetchall())
    assert got.get("stale_price", 0) == injected["stale_local_price"]
    assert got.get("misconverted", 0) == injected["wrong_conversion"]


def test_omitted_plans_are_reported(warehouse, pipeline_dirs):
    injected = Counter(d["kind"] for d in pipeline_dirs["manifest"]["injected_defects"])
    missing = warehouse.execute("select count(*) from analytics.rpt_missed_adjustments").fetchone()[0]
    assert 0 < missing <= injected["omitted_from_log"]


def test_every_batch_gets_a_verdict(warehouse, pipeline_dirs):
    rows = warehouse.execute(
        "select certification_status, count(*) from analytics.rpt_batch_scorecard group by 1").fetchall()
    assert sum(n for _, n in rows) == len(pipeline_dirs["manifest"]["workbooks"])
