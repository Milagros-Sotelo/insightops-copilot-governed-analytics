"""Explainable data quality rules and scorecard."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = (
    "record_id", "transaction_date", "area", "metric_type", "entity_name",
    "amount", "quantity", "budget", "status", "cycle_days", "source_system",
)


@dataclass(frozen=True)
class QualityOutcome:
    accepted: pd.DataFrame
    rejected: pd.DataFrame
    rule_results: pd.DataFrame
    dimensions: dict[str, float]
    quality_score: float


def _issue_rows(mask: pd.Series, rule_id: str, reason: str, severity: str = "error") -> pd.DataFrame:
    indices = mask.index[mask.fillna(False)]
    return pd.DataFrame({"row_index": indices, "rule_id": rule_id, "reason": reason, "severity": severity})


class QualityEngine:
    def validate(self, frame: pd.DataFrame, as_of: str = "2026-07-17") -> QualityOutcome:
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing_columns:
            raise ValueError(f"Missing canonical columns: {', '.join(missing_columns)}")
        data = frame.copy().reset_index(drop=True)
        dates = pd.to_datetime(data["transaction_date"], errors="coerce")
        amounts = pd.to_numeric(data["amount"], errors="coerce")
        quantities = pd.to_numeric(data["quantity"], errors="coerce")
        cycle_days = pd.to_numeric(data["cycle_days"], errors="coerce")
        issues: list[pd.DataFrame] = []
        required_missing = data[list(REQUIRED_COLUMNS)].isna().any(axis=1)
        issues.append(_issue_rows(required_missing, "DQ001", "Required field is missing"))
        issues.append(_issue_rows(dates.isna(), "DQ002", "Invalid transaction date"))
        issues.append(_issue_rows(amounts.isna(), "DQ003", "Amount is not numeric"))
        issues.append(_issue_rows(amounts.lt(0), "DQ004", "Negative amount is not allowed"))
        issues.append(_issue_rows(dates.gt(pd.Timestamp(as_of)), "DQ005", "Future transaction date"))
        issues.append(_issue_rows(data["record_id"].duplicated(keep="first"), "DQ006", "Duplicate business key"))
        issues.append(_issue_rows(~data["area"].isin(("Finanzas", "Compras", "Ventas", "Operaciones")), "DQ007", "Unknown business area"))
        issues.append(_issue_rows(quantities.lt(0) | cycle_days.lt(0), "DQ008", "Quantity and cycle days must be non-negative"))
        q1, q3 = amounts.dropna().quantile([.25, .75])
        upper = q3 + 3 * (q3 - q1)
        issues.append(_issue_rows(amounts.gt(upper), "DQ009", "Amount is an IQR outlier", "warning"))
        issue_frame = pd.concat(issues, ignore_index=True)
        hard_rejects = issue_frame.loc[issue_frame["severity"].eq("error")]
        rejected_indices = set(hard_rejects["row_index"].astype(int))
        accepted = data.loc[~data.index.isin(rejected_indices)].copy()
        rejected = data.loc[data.index.isin(rejected_indices)].copy()
        if not rejected.empty:
            reasons = hard_rejects.groupby("row_index")["reason"].agg("; ".join)
            rules = hard_rejects.groupby("row_index")["rule_id"].agg(",".join)
            rejected["rejection_reason"] = rejected.index.map(reasons)
            rejected["failed_rules"] = rejected.index.map(rules)
        dimensions = {
            "completeness": float(1 - data[list(REQUIRED_COLUMNS)].isna().sum().sum() / max(1, data[list(REQUIRED_COLUMNS)].size)),
            "validity": float(1 - (dates.isna() | amounts.isna() | amounts.lt(0)).mean()),
            "uniqueness": float(1 - data["record_id"].duplicated().mean()),
            "consistency": float(1 - (~data["area"].isin(("Finanzas", "Compras", "Ventas", "Operaciones"))).mean()),
            "timeliness": float(1 - dates.gt(pd.Timestamp(as_of)).mean()),
        }
        weights = {"completeness": .25, "validity": .25, "uniqueness": .20, "consistency": .15, "timeliness": .15}
        score = sum(dimensions[key] * weight for key, weight in weights.items()) * 100
        grouped = issue_frame.groupby(["rule_id", "reason", "severity"], dropna=False).size().reset_index(name="failed_rows")
        grouped["total_rows"] = len(data)
        grouped["pass_rate"] = 1 - grouped["failed_rows"] / max(1, len(data))
        return QualityOutcome(accepted, rejected, grouped, dimensions, round(score, 2))


def compare_quality(current: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat([history.assign(series="history"), current.assign(series="current")])
    return combined.sort_values(["source_file", "series"]).reset_index(drop=True)

