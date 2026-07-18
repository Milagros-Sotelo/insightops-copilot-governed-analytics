"""Reproducible 24-month multi-area demonstration data generator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DemoProfile:
    months: int = 24
    rows_per_area_month: int = 95
    seed: int = 20260717


AREAS = ("Finanzas", "Compras", "Ventas", "Operaciones")
AREA_METRICS = {
    "Finanzas": ("expense", "invoice", "payment"),
    "Compras": ("expense", "supplier", "order"),
    "Ventas": ("sales", "order", "margin_input"),
    "Operaciones": ("inventory", "cycle_time", "compliance"),
}
ENTITIES = {
    "Finanzas": ("Banco Delta", "Servicios Centrales", "Aseguradora Nova", "Impuestos"),
    "Compras": ("Atlas Supply", "Orion Tech", "Pampa Logistics", "Litoral Office", "Norte Industrial"),
    "Ventas": ("Cuenta Andina", "Grupo Terra", "Cliente Boreal", "Mercado Sur", "Casa Nativa"),
    "Operaciones": ("Centro Norte", "Centro Sur", "Hub Oeste", "Hub Litoral"),
}


def _periods(profile: DemoProfile) -> pd.PeriodIndex:
    return pd.period_range(end="2026-06", periods=profile.months, freq="M")


def generate_canonical(profile: DemoProfile = DemoProfile()) -> pd.DataFrame:
    rng = np.random.default_rng(profile.seed)
    rows: list[dict[str, object]] = []
    counter = 0
    periods = _periods(profile)
    for month_index, period in enumerate(periods):
        seasonality = 1 + 0.12 * np.sin((month_index % 12) / 12 * 2 * np.pi)
        growth = 1 + month_index * 0.012
        for area in AREAS:
            for _ in range(profile.rows_per_area_month):
                counter += 1
                metric_type = str(rng.choice(AREA_METRICS[area], p=(.48, .30, .22)))
                day = int(rng.integers(1, min(28, period.days_in_month) + 1))
                date = pd.Timestamp(period.start_time.year, period.start_time.month, day)
                base = {"sales": 12800, "margin_input": 7200, "expense": 6200, "payment": 5400,
                        "invoice": 4400, "supplier": 3900, "order": 3100, "inventory": 2200,
                        "cycle_time": 900, "compliance": 700}[metric_type]
                observed = max(20, rng.lognormal(np.log(base), .43) * seasonality * growth)
                if period == periods[-2] and metric_type == "expense":
                    observed *= 1.72
                if period == periods[-1] and metric_type in {"sales", "margin_input"}:
                    observed *= .69
                quantity = int(max(1, rng.normal(45 if metric_type == "inventory" else 8, 7)))
                cycle = int(max(1, rng.normal(12 if area == "Operaciones" else 7, 3)))
                status = str(rng.choice(("on_time", "approved", "late", "pending"), p=(.48, .32, .12, .08)))
                rows.append({
                    "record_id": f"AST-{counter:07d}", "transaction_date": date.date().isoformat(),
                    "area": area, "metric_type": metric_type,
                    "entity_name": str(rng.choice(ENTITIES[area])), "amount": round(observed, 2),
                    "quantity": quantity, "budget": round(base * seasonality * growth, 2),
                    "status": status, "cycle_days": cycle,
                    "source_system": {"Finanzas": "ERP_FIN", "Compras": "PROCURE", "Ventas": "CRM", "Operaciones": "WMS"}[area],
                })
    frame = pd.DataFrame(rows)
    frame["_source_period"] = pd.to_datetime(frame["transaction_date"]).dt.to_period("M").astype(str)
    # Deliberately seeded failures: missing values, duplicates, invalid future dates and negative amounts.
    missing_idx = rng.choice(frame.index, size=42, replace=False)
    frame.loc[missing_idx, "entity_name"] = None
    negative_idx = rng.choice(frame.index.difference(missing_idx), size=18, replace=False)
    frame.loc[negative_idx, "amount"] *= -1
    future_idx = rng.choice(frame.index.difference(missing_idx).difference(negative_idx), size=12, replace=False)
    frame.loc[future_idx, "transaction_date"] = "2027-02-15"
    duplicates = frame.sample(28, random_state=profile.seed)
    return pd.concat([frame, duplicates], ignore_index=True)


def source_variant(frame: pd.DataFrame, area: str, month_number: int) -> pd.DataFrame:
    subset = frame.loc[frame["area"].eq(area)].copy()
    variant = month_number % 3
    maps = (
        {"transaction_date": "fecha", "amount": "importe", "entity_name": "proveedor", "quantity": "cantidad", "budget": "presupuesto", "status": "estado", "source_system": "sistema"},
        {"transaction_date": "date", "amount": "net_value", "entity_name": "supplier_name", "quantity": "units", "budget": "target", "cycle_days": "lead_time"},
        {"transaction_date": "posting_date", "amount": "value", "entity_name": "vendor", "metric_type": "kpi_type", "source_system": "origin"},
    )
    return subset.rename(columns=maps[variant])


def write_demo_files(output_dir: str | Path, profile: DemoProfile = DemoProfile()) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    canonical = generate_canonical(profile)
    paths: list[Path] = []
    for month_number, period in enumerate(_periods(profile)):
        period_text = str(period)
        for area in AREAS:
            monthly = canonical.loc[canonical["_source_period"].eq(period_text)].drop(columns="_source_period")
            monthly = source_variant(monthly, area, month_number)
            path = output / f"{period_text}_{area.lower()}.csv"
            separator = ";" if month_number % 4 == 0 else ","
            encoding = "utf-8-sig" if month_number % 5 == 0 else "utf-8"
            monthly.to_csv(path, index=False, sep=separator, encoding=encoding)
            paths.append(path)
    # An exact duplicate validates hash-based deduplication without contaminating accepted records.
    duplicate = output / "2026-06_ventas_DUPLICATE.csv"
    original = output / "2026-06_ventas.csv"
    duplicate.write_bytes(original.read_bytes())
    paths.append(duplicate)
    return paths
