"""Monthly report drafting and human approval workflow."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .audit import AuditEvent, AuditLog


REPORT_STATES = ("Draft", "Under Review", "Approved", "Rejected", "Published")
ALLOWED_TRANSITIONS = {
    "Draft": {"Under Review"}, "Under Review": {"Approved", "Rejected"},
    "Rejected": {"Draft"}, "Approved": {"Published"}, "Published": set(),
}


@dataclass
class ReportDraft:
    report_id: str
    period: str
    title: str
    executive_summary: str
    kpi_highlights: list[str]
    anomalies: list[str]
    data_quality: str
    possible_causes: list[str]
    recommendations: list[str]
    limitations: list[str]
    sources: list[str]
    status: str = "Draft"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_by: str | None = None

    def transition(self, new_status: str, actor: str, audit: AuditLog) -> None:
        if new_status not in REPORT_STATES or new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"Invalid report transition: {self.status} -> {new_status}")
        old_status = self.status
        self.status = new_status
        if new_status == "Approved":
            self.approved_by = actor
        audit.record(AuditEvent("report_status_changed", actor, "report", self.report_id, {"from": old_status, "to": new_status}))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def create_monthly_report(metrics: pd.DataFrame, anomalies: pd.DataFrame, quality_runs: pd.DataFrame) -> ReportDraft:
    period = str(metrics["period"].max())
    current = metrics.loc[metrics["period"].eq(period)]
    kpis = [f"{row.name}: {row.value:,.2f}" for row in current.head(5).itertuples(index=False)]
    alerts = anomalies.loc[anomalies["period"].eq(period)] if not anomalies.empty else anomalies
    anomaly_text = [f"{row.metric_name}: {row.variation:+.1%} vs. esperado ({row.severity})" for row in alerts.head(6).itertuples(index=False)]
    score = float(quality_runs["quality_score"].mean()) if not quality_runs.empty else 0.0
    summary = f"Asteria Services cerró {period} con {len(alerts)} señales analíticas abiertas y una calidad promedio de {score:.2f}/100."
    return ReportDraft(
        report_id=f"RPT-{period}", period=period, title=f"Monthly Analytics Brief · {period}", executive_summary=summary,
        kpi_highlights=kpis, anomalies=anomaly_text,
        data_quality=f"Quality score promedio: {score:.2f}/100. Las ejecuciones rechazadas no alimentan métricas.",
        possible_causes=["Mix de transacciones o cambios de volumen.", "Cambios de fuente o deterioro de calidad.", "Efectos estacionales; requieren validación humana."],
        recommendations=["Revisar primero alertas críticas y sus archivos fuente.", "Validar el desvío con el propietario de la métrica.", "Aprobar el reporte solo después de documentar la conclusión."],
        limitations=["Las anomalías no prueban causalidad.", "El modo determinístico resume únicamente vistas aprobadas."],
        sources=["vw_metric_monitoring", "vw_anomaly_center", "vw_quality_summary"],
    )


def save_report(report: ReportDraft, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return target

