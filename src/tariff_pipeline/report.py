"""Print the batch scorecard (certified / needs_review) after a dbt build.

On DuckDB it also writes data/exports/*.csv so the marts can be opened in
Power BI or Excel without a database driver.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

EXPORTS = ["rpt_batch_scorecard", "fct_tariff_history", "fct_fx_alignment",
           "rpt_missed_adjustments", "rpt_revenue_split_check", "dim_plan"]
QUERY = """
select requirement_id, effective_date, plans_logged, plans_aligned, plans_stale,
       plans_misconverted, plans_missing, split_errors, rows_quarantined,
       certification_status
from {schema}.rpt_batch_scorecard
order by batch_seq
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", choices=["duckdb", "bigquery"],
                    default=os.getenv("WAREHOUSE_TARGET", "duckdb"))
    ap.add_argument("--duckdb-path", default=os.getenv("DUCKDB_PATH", "data/warehouse.duckdb"))
    ap.add_argument("--exports", default="data/exports")
    a = ap.parse_args()

    if a.target == "duckdb":
        import duckdb

        con = duckdb.connect(a.duckdb_path, read_only=True)
        df = con.execute(QUERY.format(schema="analytics")).df()
        out = Path(a.exports)
        out.mkdir(parents=True, exist_ok=True)
        for t in EXPORTS:
            con.execute(f"copy analytics.{t} to '{(out / t).as_posix()}.csv' (header)")
        con.close()
    else:
        from google.cloud import bigquery

        project = os.environ["GCP_PROJECT"]
        df = bigquery.Client(project=project).query(
            QUERY.format(schema=f"`{project}.analytics`")).to_dataframe()

    print(df.to_string(index=False))
    review = int((df["certification_status"] == "needs_review").sum())
    print(f"\n{len(df)} price logs, {review} need review")


if __name__ == "__main__":
    main()
