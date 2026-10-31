"""Load staged CSVs into the warehouse `raw` layer.

Targets
-------
duckdb    local file warehouse (default; no cloud account needed)
bigquery  uploads each CSV to a GCS landing bucket, then runs a BigQuery load
          job into the `raw` dataset (WRITE_TRUNCATE, every column STRING).

Columns are loaded as text on purpose: casting happens in dbt staging models,
where bad values surface as failing tests instead of failed loads.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

TABLES = ["tariff_batches", "prepaid_plans", "postpaid_plans", "revenue_split",
          "b2b_access", "b2b_inbound_access", "quarantine"]


def _header(path: Path) -> list[str]:
    with open(path, newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh))


def load_duckdb(staged: Path, db_path: str) -> dict:
    import duckdb  # imported lazily so the BigQuery path does not need it

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(db_path)
    con.execute("create schema if not exists raw")
    counts = {}
    for t in TABLES:
        f = staged / f"{t}.csv"
        cols = _header(f)
        types = ", ".join(f"'{c}': 'VARCHAR'" for c in cols)
        con.execute(
            f"create or replace table raw.{t} as "
            f"select * from read_csv('{f.as_posix()}', header=true, columns={{{types}}})"
        )
        counts[t] = con.execute(f"select count(*) from raw.{t}").fetchone()[0]
    con.close()
    return counts


def load_bigquery(staged: Path, project: str, bucket: str, dataset: str = "raw",
                  location: str = "US") -> dict:
    from google.cloud import bigquery, storage

    gcs = storage.Client(project=project).bucket(bucket)
    bq = bigquery.Client(project=project, location=location)
    counts = {}
    for t in TABLES:
        f = staged / f"{t}.csv"
        blob = gcs.blob(f"staged/{t}.csv")
        blob.upload_from_filename(str(f))
        schema = [bigquery.SchemaField(c, "STRING") for c in _header(f)]
        job = bq.load_table_from_uri(
            f"gs://{bucket}/staged/{t}.csv",
            f"{project}.{dataset}.{t}",
            job_config=bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1,
                schema=schema,
                allow_quoted_newlines=True,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            ),
        )
        job.result()
        counts[t] = bq.get_table(f"{project}.{dataset}.{t}").num_rows
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--staged", default="data/staged")
    ap.add_argument("--target", choices=["duckdb", "bigquery"],
                    default=os.getenv("WAREHOUSE_TARGET", "duckdb"))
    ap.add_argument("--duckdb-path", default=os.getenv("DUCKDB_PATH", "data/warehouse.duckdb"))
    ap.add_argument("--project", default=os.getenv("GCP_PROJECT"))
    ap.add_argument("--bucket", default=os.getenv("GCS_LANDING_BUCKET"))
    ap.add_argument("--location", default=os.getenv("BQ_LOCATION", "US"))
    a = ap.parse_args()
    staged = Path(a.staged)
    if a.target == "duckdb":
        counts = load_duckdb(staged, a.duckdb_path)
    else:
        if not (a.project and a.bucket):
            ap.error("bigquery target needs --project and --bucket (or GCP_PROJECT / GCS_LANDING_BUCKET)")
        counts = load_bigquery(staged, a.project, a.bucket, location=a.location)
    for t, n in counts.items():
        print(f"raw.{t}: {n} rows")


if __name__ == "__main__":
    main()
