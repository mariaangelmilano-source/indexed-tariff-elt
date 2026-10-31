"""Synthetic price-log generator.

Builds Excel workbooks that mimic the layout of a telecom "price log"
(bitácora de precios): one workbook per tariff adjustment, with one sheet per
business line, prices indexed to USD and converted at an official exchange rate.

Everything here is synthetic. The company ("M Communications"), plan names,
codes, requirement numbers and exchange rates are invented. A small, seeded
share of data-quality defects is injected on purpose so the downstream
revenue-assurance checks have something to catch.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from .config import load_layout


@dataclass
class Plan:
    sheet: str
    cbs_code: str
    plan_name: str
    price_usd: float
    product: str
    product_type: str
    platform_code: str
    bo_code: str
    extra: dict = field(default_factory=dict)


def _catalog(rng: random.Random) -> list[Plan]:
    plans: list[Plan] = []
    code = 40100

    def add(sheet, name, usd, product, ptype, platform, bo, **extra):
        nonlocal code
        code += rng.randint(1, 7)
        plans.append(Plan(sheet, str(code), name, usd, product, ptype, platform, bo, extra))

    for gb, usd in [(2, 3.5), (4, 5.0), (6, 7.0), (10, 9.0), (25, 15.0), (50, 24.0)]:
        add("prepaid_plans", f"M Plus {gb} GB", usd, "Movil", "Plan", "1101", "PRE",
            rating_unit="MB")
    for name, usd in [("Voice Pack 100 min", 2.0), ("SMS Pack 500", 1.0), ("Social Pack", 1.5),
                      ("Roaming Day Pass", 4.0)]:
        add("prepaid_plans", name, usd, "Movil", "SVA", "1102", "PRE", rating_unit="UNIT")
    for gb, usd in [(10, 12.0), (25, 18.0), (50, 28.0), (100, 40.0)]:
        add("postpaid_plans", f"M Control {gb} GB", usd, "Movil", "Plan", "1201", "POS",
            segment="Consumer")
    for name, usd in [("Business Plus M2M", 6.0), ("Business APN", 9.0),
                      ("Fleet Tracking M2M", 4.5), ("Business 50 GB", 32.0)]:
        add("postpaid_plans", name, usd, "Movil", "Plan", "1202", "POS", segment="Business")
    for bw, km, usd in [(2048, "N/A", 85.0), (4096, "N/A", 140.0), (10240, "N/A", 260.0),
                        (2048, "<50km", 120.0), (10240, "<50km", 330.0)]:
        add("b2b_access", f"Private Access {bw // 1024} Mbps", usd, "CPA", "Plan", "1401", "CPA",
            bandwidth_kbps=str(bw), distance=km)
    for bw, usd in [(1024, 60.0), (2048, 95.0), (4096, 150.0)]:
        add("b2b_inbound_access", f"Inbound Access {bw // 1024} Mbps", usd, "CPA", "Plan", "1402",
            "CPA", bandwidth_kbps=str(bw), distance="N/A")
    return plans


def _revenue_split(plan: Plan, rng: random.Random) -> list[tuple[str, str, float]]:
    """Split a bundle price into value-added components (voice, sms, data)."""
    voice = rng.choice([10.0, 12.5, 15.0])
    sms = rng.choice([2.5, 5.0])
    data = round(100.0 - voice - sms, 2)
    base = int(plan.cbs_code) * 10
    return [
        (str(base + 1), "Voice", voice),
        (str(base + 2), "SMS", sms),
        (str(base + 3), "Data", data),
    ]


def _write_sheet(ws, title: str, header_row: int, headers: list[str], rows: list[list]):
    ws["A1"] = title
    ws["A1"].font = Font(bold=True)
    ws["A2"] = "Synthetic data - M Communications (fictitious company)"
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=header_row, column=col, value=h)
        c.font = Font(bold=True)
    for r, values in enumerate(rows, start=header_row + 1):
        for col, v in enumerate(values, start=1):
            ws.cell(row=r, column=col, value=v)


def generate(out_dir: Path, start: date, months: int, seed: int, defect_rate: float) -> dict:
    rng = random.Random(seed)
    layout = load_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    plans = _catalog(rng)
    split_by_plan = {p.cbs_code: _revenue_split(p, rng)
                     for p in plans if p.sheet == "prepaid_plans" and p.product_type == "Plan"}

    fx = 40.0
    req = 5000
    previous_local: dict[str, float] = {}
    manifest = {"seed": seed, "workbooks": [], "injected_defects": []}

    month_start = start.replace(day=1)
    for m in range(months):
        first = (month_start + timedelta(days=32 * m)).replace(day=1)
        cuts = rng.randint(3, 6)
        days = sorted(rng.sample(range(1, 28), cuts))
        for cut, day in enumerate(days, start=1):
            fx = round(fx * (1 + rng.uniform(0.01, 0.06)), 4)
            req += rng.randint(3, 40)
            eff = first.replace(day=day)
            requirement_id = f"REQ-{req}"
            if rng.random() < 0.08:  # occasional USD list-price review
                victim = rng.choice(plans)
                victim.price_usd = round(victim.price_usd * 1.1, 2)

            wb = Workbook()
            meta = wb.active
            meta.title = layout["metadata_sheet"]["name"]
            mf = layout["metadata_sheet"]["fields"]
            meta.append([mf["requirement_id"], requirement_id])
            meta.append([mf["effective_date"], eff.strftime("%d/%m/%Y")])
            meta.append([mf["official_fx_rate"], fx])
            meta.append([mf["cut_number"], cut])

            def defect(requirement_id, kind: str, **info):
                manifest["injected_defects"].append(
                    {"requirement_id": requirement_id, "kind": kind, **info})

            for key, spec in layout["sheets"].items():
                headers = list(spec["columns"].keys())
                field_of = spec["columns"]
                rows: list[list] = []
                if key == "revenue_split":
                    for p in plans:
                        if p.cbs_code not in split_by_plan:
                            continue
                        local = round(p.price_usd * fx, 2)
                        comps = split_by_plan[p.cbs_code]
                        if rng.random() < defect_rate / 2:
                            comps = [(c, n, pct + (5.0 if n == "Data" else 0.0))
                                     for c, n, pct in comps]
                            defect("split_not_100", cbs_code=p.cbs_code)
                        for comp_code, comp_name, pct in comps:
                            vals = {"plan_cbs_code": p.cbs_code, "plan_name": p.plan_name,
                                    "component_code": comp_code, "component_name": comp_name,
                                    "split_pct": pct,
                                    "component_amount_local": round(local * pct / 100, 2)}
                            rows.append([vals.get(field_of[h]) for h in headers])
                else:
                    for p in [p for p in plans if p.sheet == key]:
                        local = round(p.price_usd * fx, 2)
                        roll = rng.random()
                        if roll < defect_rate * 0.25 and p.cbs_code in previous_local:
                            defect("omitted_from_log", cbs_code=p.cbs_code)
                            continue
                        if roll < defect_rate * 0.5 and p.cbs_code in previous_local:
                            local = previous_local[p.cbs_code]
                            defect("stale_local_price", cbs_code=p.cbs_code)
                        elif roll < defect_rate * 0.75:
                            local = round(local * rng.choice([0.9, 1.1]), 2)
                            defect("wrong_conversion", cbs_code=p.cbs_code)
                        previous_local[p.cbs_code] = local
                        vals = {"product": p.product, "product_type": p.product_type,
                                "platform_code": p.platform_code, "bo_code": p.bo_code,
                                "cbs_code": p.cbs_code, "plan_name": p.plan_name,
                                "price_usd": p.price_usd, "price_local_ex_vat": local, **p.extra}
                        rows.append([vals.get(field_of[h]) for h in headers])
                    if rows and rng.random() < defect_rate:
                        broken = list(rows[0])
                        broken[headers.index(next(h for h, f in field_of.items()
                                                  if f == "cbs_code"))] = None
                        rows.append(broken)
                        defect("missing_cbs_code", sheet=key)
                    if rows and rng.random() < defect_rate / 2:
                        rows.append(list(rows[-2]))
                        defect("duplicate_row", sheet=key)
                ws = wb.create_sheet(spec["sheet_name"])
                _write_sheet(ws, spec["sheet_name"], spec["header_row"], headers, rows)

            name = f"bitacora_{eff.isoformat()}_{requirement_id}.xlsx"
            wb.save(out_dir / name)
            manifest["workbooks"].append(name)

    (out_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/landing")
    ap.add_argument("--start", default="2026-01-01")
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--defect-rate", type=float, default=0.06)
    a = ap.parse_args()
    m = generate(Path(a.out), date.fromisoformat(a.start), a.months, a.seed, a.defect_rate)
    print(f"{len(m['workbooks'])} workbooks, {len(m['injected_defects'])} injected defects -> {a.out}")


if __name__ == "__main__":
    main()
