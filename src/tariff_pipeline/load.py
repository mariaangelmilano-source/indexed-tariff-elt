"""Load staged CSVs into the warehouse `raw` layer.

Targets
-------
duckdb    local file warehouse (default; no cloud account needed)
bigquery  loads each CSV into the `raw` dataset (WRITE_TRUNCATE, every column
          STRING). With a GCS bucket configured, files are staged in the bucket
          first; without one, they are loaded straight from disk, which works in
          the BigQuery sandbox (no billing account, no credit card).

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


def load_bigquery(staged: Path, project: str, bucket: str | None = None, dataset: str = "raw",
                  location: str = "US") -> dict:
    from google.cloud import bigquery

    bq = bigquery.Client(project=project, location=location)
    ds = bigquery.Dataset(f"{project}.{dataset}")
    ds.location = location
    bq.create_dataset(ds, exists_ok=True)
    gcs = None
    if bucket:
        from google.cloud import storage

        gcs = storage.Client(project=project).bucket(bucket)

    counts = {}
    for t in TABLES:
        f = staged / f"{t}.csv"
        cfg = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            schema=[bigquery.SchemaField(c, "STRING") for c in _header(f)],
            allow_quoted_newlines=True,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        table_id = f"{project}.{dataset}.{t}"
        if gcs is not None:
            gcs.blob(f"staged/{t}.csv").upload_from_filename(str(f))
            job = bq.load_table_from_uri(f"gs://{bucket}/staged/{t}.csv", table_id, job_config=cfg)
        else:
            with open(f, "rb") as fh:
                job = bq.load_table_from_file(fh, table_id, job_config=cfg)
        job.result()
        counts[t] = bq.get_table(table_id).num_rows
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
        if not a.project:
            ap.error("bigquery target needs --project (or GCP_PROJECT)")
        counts = load_bigquery(staged, a.project, a.bucket or None, location=a.location)
    for t, n in counts.items():
        print(f"raw.{t}: {n} rows")


if __name__ == "__main__":
    main()
