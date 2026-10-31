.PHONY: install data extract load dbt report pipeline test cloud clean

PY ?= python
export PYTHONPATH := src

install:
	$(PY) -m pip install -r requirements-dev.txt

data:            ## generate synthetic price logs
	$(PY) -m tariff_pipeline.generate --out data/landing --months 6 --seed 42

extract:
	$(PY) -m tariff_pipeline.extract --landing data/landing --staged data/staged

load:
	$(PY) -m tariff_pipeline.load --target duckdb

dbt:
	cd dbt && DUCKDB_PATH=../data/warehouse.duckdb dbt build --profiles-dir . --target duckdb

report:
	$(PY) -m tariff_pipeline.report --target duckdb

pipeline: data extract load dbt report   ## end-to-end, local, no cloud account needed

test:
	$(PY) -m pytest -q

cloud: data extract   ## same pipeline on BigQuery (needs .env with GCP vars)
	$(PY) -m tariff_pipeline.load --target bigquery
	cd dbt && dbt build --profiles-dir . --target bigquery
	$(PY) -m tariff_pipeline.report --target bigquery

clean:
	rm -rf data dbt/target dbt/logs
