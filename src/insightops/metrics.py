"""Governed metric catalog and reproducible KPI calculations."""

from __future__ import annotations

import pandas as pd
import numpy as np


def metric_catalog() -> pd.DataFrame:
    rows = [
        ("NET_SALES", "Ventas netas", "Suma de ventas aceptadas", "SUM(amount WHERE metric_type=sales)", "month", "vw_metric_monitoring", "Commercial Analytics", "monthly", 500000, 2500000, "higher"),
        ("GROSS_MARGIN", "Margen bruto", "Ventas menos costo imputado, sobre ventas", "(sales-margin_input)/sales", "month", "vw_metric_monitoring", "Finance", "monthly", .25, .55, "higher"),
        ("EXPENSES", "Gastos", "Suma de egresos aceptados", "SUM(amount WHERE metric_type=expense)", "month", "vw_metric_monitoring", "Finance", "monthly", 200000, 1200000, "lower"),
        ("ORDERS", "Órdenes", "Cantidad de registros de orden", "COUNT(record_id WHERE metric_type=order)", "month", "vw_metric_monitoring", "Operations", "monthly", 40, 400, "higher"),
        ("INVOICES", "Facturas", "Cantidad de facturas procesadas", "COUNT(record_id WHERE metric_type=invoice)", "month", "vw_metric_monitoring", "Finance", "monthly", 20, 250, "neutral"),
        ("PAYMENTS", "Pagos", "Importe total de pagos", "SUM(amount WHERE metric_type=payment)", "month", "vw_metric_monitoring", "Treasury", "monthly", 100000, 1000000, "neutral"),
        ("SUPPLIERS", "Proveedores activos", "Proveedores únicos con actividad", "COUNT(DISTINCT entity_name)", "month", "vw_metric_monitoring", "Procurement", "monthly", 2, 80, "neutral"),
        ("INVENTORY", "Inventario promedio", "Unidades promedio informadas", "AVG(quantity WHERE metric_type=inventory)", "month", "vw_metric_monitoring", "Operations", "monthly", 20, 80, "neutral"),
        ("CYCLE_TIME", "Tiempo de ciclo", "Días promedio de procesamiento", "AVG(cycle_days)", "month", "vw_metric_monitoring", "Operations", "monthly", 1, 18, "lower"),
        ("COMPLIANCE", "Cumplimiento", "Porcentaje aprobado o en término", "approved_or_on_time/records", "month", "vw_metric_monitoring", "Operations", "monthly", .72, 1, "higher"),
    ]
    columns = ["metric_id", "name", "definition", "formula", "granularity", "source", "owner", "frequency", "expected_min", "expected_max", "improvement_direction"]
    catalog = pd.DataFrame(rows, columns=columns)
    catalog["effective_date"] = "2024-07-01"
    return catalog


def calculate_metrics(accepted: pd.DataFrame) -> pd.DataFrame:
    data = accepted.copy()
    data["transaction_date"] = pd.to_datetime(data["transaction_date"])
    data["period"] = data["transaction_date"].dt.to_period("M").astype(str)
    data["amount"] = pd.to_numeric(data["amount"], errors="coerce").fillna(0)
    data["budget"] = pd.to_numeric(data["budget"], errors="coerce").fillna(0)
    data["quantity"] = pd.to_numeric(data["quantity"], errors="coerce")
    data["cycle_days"] = pd.to_numeric(data["cycle_days"], errors="coerce")
    results: list[dict[str, object]] = []
    for period, group in data.groupby("period"):
        sales = group.loc[group["metric_type"].eq("sales"), "amount"].sum()
        costs = group.loc[group["metric_type"].eq("margin_input"), "amount"].sum()
        expense = group.loc[group["metric_type"].eq("expense"), "amount"].sum()
        metric_values = {
            "NET_SALES": sales,
            "GROSS_MARGIN": (sales - costs) / sales if sales else np.nan,
            "EXPENSES": expense,
            "ORDERS": group["metric_type"].eq("order").sum(),
            "INVOICES": group["metric_type"].eq("invoice").sum(),
            "PAYMENTS": group.loc[group["metric_type"].eq("payment"), "amount"].sum(),
            "SUPPLIERS": group.loc[group["metric_type"].eq("supplier"), "entity_name"].nunique(),
            "INVENTORY": group.loc[group["metric_type"].eq("inventory"), "quantity"].mean(),
            "CYCLE_TIME": group["cycle_days"].mean(),
            "COMPLIANCE": group["status"].isin(("approved", "on_time")).mean(),
        }
        budget_map = {
            "NET_SALES": group.loc[group["metric_type"].eq("sales"), "budget"].sum(),
            "EXPENSES": group.loc[group["metric_type"].eq("expense"), "budget"].sum(),
        }
        for metric_id, value in metric_values.items():
            budget = budget_map.get(metric_id, np.nan)
            results.append({"period": period, "metric_id": metric_id, "value": float(value), "budget": float(budget) if pd.notna(budget) else np.nan})
    result = pd.DataFrame(results)
    result = result.merge(metric_catalog(), on="metric_id", how="left", validate="many_to_one")
    result["budget_variance"] = (result["value"] - result["budget"]) / result["budget"].replace(0, np.nan)
    return result.sort_values(["period", "metric_id"]).reset_index(drop=True)

