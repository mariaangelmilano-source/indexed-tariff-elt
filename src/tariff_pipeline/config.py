from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LAYOUT_FILE = ROOT / "config" / "sheets.yml"


@lru_cache(maxsize=1)
def load_layout(path: str | None = None) -> dict:
    with open(path or LAYOUT_FILE, encoding="utf-8") as fh:
        return yaml.safe_load(fh)
