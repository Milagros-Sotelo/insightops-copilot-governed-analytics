"""Grounded deterministic analysis copilot with optional provider boundary."""

from __future__ import annotations

import os
import re
from typing import Protocol

import pandas as pd

from .audit import AuditEvent, AuditLog
from .models import CopilotAnswer
from .security import safe_question, validate_read_only_sql


class LLMProvider(Protocol):
    def complete(self, system: str, context: str, question: str) -> str: ...


def _format_value(metric_id: str, value: float) -> str:
    if metric_id in {"GROSS_MARGIN", "COMPLIANCE"}:
        return f"{value * 100:.1f}%"
    if metric_id in {"NET_SALES", "EXPENSES", "PAYMENTS"}:
        return f"US$ {value:,.0f}"
    return f"{value:,.1f}"


class DeterministicCopilot:
    def __init__(self, metrics: pd.DataFrame, anomalies: pd.DataFrame, quality: pd.DataFrame, audit: AuditLog | None = None) -> None:
        self.metrics = metrics.copy()
        self.anomalies = anomalies.copy()
        self.quality = quality.copy()
        self.audit = audit or AuditLog()

    @property
    def latest_period(self) -> str:
        return str(self.metrics["period"].max())

    def answer(self, question: str, actor: str = "demo.user@asteria.example") -> CopilotAnswer:
        cleaned = safe_question(question)
        lowered = cleaned.lower()
        if any(token in lowered for token in ("anomal", "desvi", "alert", "prior")):
            result = self._anomalies(cleaned)
        elif any(token in lowered for token in ("calidad", "archivo", "quality")):
            result = self._quality(cleaned)
        elif any(token in lowered for token in ("proveedor", "concentra")):
            result = self._insufficient(cleaned, "El mart aprobado no contiene el detalle de concentración por proveedor en esta ejecución.")
        elif any(token in lowered for token in ("margen", "venta", "gasto", "kpi")):
            result = self._metric(cleaned)
        else:
            result = self._insufficient(cleaned, "No pude vincular la pregunta con una métrica gobernada o una vista aprobada.")
        self.audit.record(AuditEvent(
            event_type="copilot_question", actor=actor, object_type="copilot_interaction",
            object_id=f"COP-{len(self.audit.events)+1:05d}",
            details={"question": cleaned, "metrics": list(result.metrics), "sources": list(result.sources), "sufficient_data": result.sufficient_data},
        ))
        return result

    def _anomalies(self, question: str) -> CopilotAnswer:
        latest = self.anomalies.loc[self.anomalies["period"].eq(self.latest_period)].copy()
        sql = validate_read_only_sql(
            f"SELECT metric_id, metric_name, observed_value, expected_value, variation, severity, explanation FROM vw_anomaly_center WHERE period = '{self.latest_period}' ORDER BY severity LIMIT 20"
        )
        if latest.empty:
            return self._insufficient(question, "No existen anomalías abiertas para el último período.")
        latest = latest.sort_values("severity").head(5)
        facts = tuple(
            f"{row.metric_name}: {_format_value(row.metric_id, row.observed_value)} ({row.variation:+.1%} vs. esperado)"
            for row in latest.itertuples(index=False)
        )
        answer = f"En {self.latest_period} detecté {len(latest)} desvíos prioritarios. " + " ".join(facts[:3])
        return CopilotAnswer(question, answer, sql, ("vw_anomaly_center",), tuple(latest["metric_id"]), self.latest_period, facts,
                             ("Las causas requieren validación con los responsables de cada fuente.",),
                             "Los desvíos son señales analíticas, no explicaciones causales confirmadas.", True)

    def _quality(self, question: str) -> CopilotAnswer:
        sql = validate_read_only_sql(
            "SELECT source_file, quality_score, rows_received, rows_rejected, status FROM vw_quality_summary ORDER BY quality_score ASC LIMIT 20"
        )
        if self.quality.empty:
            return self._insufficient(question, "No hay ejecuciones de calidad disponibles.")
        worst = self.quality.sort_values("quality_score").iloc[0]
        facts = (
            f"La menor calidad corresponde a {worst['source_file']} con {worst['quality_score']:.2f} puntos.",
            f"Se rechazaron {int(worst['rows_rejected'])} de {int(worst['rows_received'])} registros.",
        )
        answer = f"El archivo que requiere revisión primero es {worst['source_file']}: {worst['quality_score']:.2f}/100."
        return CopilotAnswer(question, answer, sql, ("vw_quality_summary",), ("DATA_QUALITY_SCORE",), self.latest_period, facts, (),
                             "La calidad se calcula sobre cinco dimensiones y reglas versionadas.", True)

    def _metric(self, question: str) -> CopilotAnswer:
        metric_id = "GROSS_MARGIN" if "margen" in question.lower() else "EXPENSES" if "gasto" in question.lower() else "NET_SALES"
        sql = validate_read_only_sql(
            f"SELECT period, metric_id, value, budget, budget_variance FROM vw_metric_monitoring WHERE metric_id = '{metric_id}' ORDER BY period DESC LIMIT 13"
        )
        series = self.metrics.loc[self.metrics["metric_id"].eq(metric_id)].sort_values("period")
        if len(series) < 2:
            return self._insufficient(question, "No existen dos períodos comparables para esa métrica.")
        current, previous = series.iloc[-1], series.iloc[-2]
        change = (current["value"] - previous["value"]) / previous["value"] if previous["value"] else float("nan")
        facts = (
            f"{current['name']} en {current['period']}: {_format_value(metric_id, current['value'])}.",
            f"Variación mensual: {change:+.1%}.",
        )
        hypotheses = ("El cambio puede relacionarse con volumen, mix o calidad de fuente; esta vista no permite confirmar causalidad.",)
        return CopilotAnswer(question, " ".join(facts), sql, ("vw_metric_monitoring",), (metric_id,), str(current["period"]), facts, hypotheses,
                             "Respuesta generada exclusivamente desde el catálogo y la vista aprobada.", True)

    def _insufficient(self, question: str, reason: str) -> CopilotAnswer:
        return CopilotAnswer(question, reason, "", (), (), self.latest_period, (), (), "No se inventaron cifras ni consultas.", False)


def provider_mode() -> str:
    provider = os.getenv("LLM_PROVIDER", "disabled").strip().lower()
    return "deterministic" if provider in {"", "disabled", "none"} else provider
