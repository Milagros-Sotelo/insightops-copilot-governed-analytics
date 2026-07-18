"""Interpretable KPI anomaly detection with auditable explanations."""

from __future__ import annotations

import numpy as np
import pandas as pd


def robust_z_score(series: pd.Series) -> pd.Series:
    median = series.median()
    mad = (series - median).abs().median()
    if not mad or pd.isna(mad):
        return pd.Series(0.0, index=series.index)
    return 0.6745 * (series - median) / mad


def isolation_forest_flags(series: pd.Series) -> pd.Series:
    """Return deterministic Isolation Forest flags when scikit-learn is available."""
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        return pd.Series(False, index=series.index)
    valid = series.dropna()
    if len(valid) < 12:
        return pd.Series(False, index=series.index)
    model = IsolationForest(n_estimators=150, contamination=.08, random_state=20260717)
    labels = model.fit_predict(valid.to_numpy().reshape(-1, 1))
    result = pd.Series(False, index=series.index)
    result.loc[valid.index] = labels == -1
    return result


def detect_anomalies(metrics: pd.DataFrame) -> pd.DataFrame:
    findings: list[dict[str, object]] = []
    for metric_id, group in metrics.groupby("metric_id"):
        ordered = group.sort_values("period").copy()
        ordered["expected"] = ordered["value"].shift(1).rolling(6, min_periods=3).median()
        ordered["robust_z"] = robust_z_score(ordered["value"])
        ordered["isolation_flag"] = isolation_forest_flags(ordered["value"])
        ordered["relative_change"] = ordered["value"].pct_change()
        for row in ordered.itertuples(index=False):
            methods: list[str] = []
            if abs(row.robust_z) >= 2.7:
                methods.append("robust_z_score")
            if row.isolation_flag:
                methods.append("isolation_forest")
            if pd.notna(row.relative_change) and abs(row.relative_change) >= .25:
                methods.append("month_over_month_threshold")
            if pd.notna(row.budget_variance) and abs(row.budget_variance) >= .20:
                methods.append("budget_variance")
            if row.value < row.expected_min or row.value > row.expected_max:
                methods.append("catalog_range")
            if not methods:
                continue
            severity = "critical" if abs(row.robust_z) >= 4 or (pd.notna(row.budget_variance) and abs(row.budget_variance) >= .4) else "high" if abs(row.robust_z) >= 2.7 else "medium"
            expected = row.expected if pd.notna(row.expected) else (row.budget if pd.notna(row.budget) else np.nan)
            variation = (row.value - expected) / expected if pd.notna(expected) and expected != 0 else row.relative_change
            findings.append({
                "metric_id": metric_id, "metric_name": row.name, "period": row.period,
                "observed_value": row.value, "expected_value": expected,
                "variation": variation, "method": ", ".join(methods), "severity": severity,
                "explanation": f"{row.name} se apartó del patrón histórico o del rango gobernado; revisar las fuentes antes de atribuir una causa.",
                "source": row.source, "review_status": "open",
            })
    return pd.DataFrame(findings).sort_values(["period", "severity", "metric_id"], ascending=[False, True, True]).reset_index(drop=True)
