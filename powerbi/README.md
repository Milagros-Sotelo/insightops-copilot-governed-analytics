# Power BI implementation guide

This repository contains connection-ready views and DAX, not a claimed PBIX artifact.

1. Connect Power BI Desktop to PostgreSQL using a read-only `insightops_readonly` user.
2. Import `vw_control_center`, `vw_quality_summary`, `vw_metric_monitoring` and `vw_anomaly_center`.
3. Add a calendar table covering the minimum and maximum period, mark it as the date table and relate it one-to-many to analytical dates.
4. Keep the metric catalog in a one-to-many relationship with metric results.
5. Paste the measures from `measures.dax` and validate totals against `data/demo/marts`.

`power_query.pq` provides a parameterized PostgreSQL query with explicit types and source filtering. Define `ParameterServer` and `ParameterDatabase` in Power BI before pasting it into the Advanced Editor.

Recommended pages:

- Quality: score, rejection rate, failing rules and problematic sources.
- KPI: metric selector, actual versus budget, monthly variation and definition tooltip.
- Anomalies: severity, method, expected versus observed, review status and drill-through.
- Control: run status, processing duration, rows and source lineage.

For refresh, use a gateway for private PostgreSQL, store credentials in the service, and schedule refresh after the pipeline completes. Never embed credentials in PBIX or source files.
