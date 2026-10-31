FROM python:3.12-slim
WORKDIR /app
COPY requirements*.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends make && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements-gcp.txt
COPY . .
ENV PYTHONPATH=/app/src
# Default: full local run on DuckDB. Override CMD to `make cloud` for BigQuery.
CMD ["make", "pipeline"]
