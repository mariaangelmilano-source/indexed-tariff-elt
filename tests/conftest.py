import json
from datetime import date
from pathlib import Path

import pytest

from tariff_pipeline.extract import extract
from tariff_pipeline.generate import generate


@pytest.fixture(scope="session")
def pipeline_dirs(tmp_path_factory):
    root = tmp_path_factory.mktemp("run")
    landing, staged = root / "landing", root / "staged"
    manifest = generate(landing, date(2026, 1, 1), months=4, seed=7, defect_rate=0.08)
    summary = extract(landing, staged)
    return {"root": root, "landing": landing, "staged": staged,
            "manifest": manifest, "summary": summary}


def read_manifest(landing: Path) -> dict:
    return json.loads((landing / "_manifest.json").read_text())
