"""Canonical schema mapping with templates, aliases and human review."""

from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

import pandas as pd


ALIASES: dict[str, tuple[str, ...]] = {
    "record_id": ("record_id", "id", "transaction_id", "registro_id", "document_id"),
    "transaction_date": ("transaction_date", "date", "fecha", "fecha_operacion", "posting_date"),
    "area": ("area", "department", "sector", "business_area"),
    "metric_type": ("metric_type", "type", "tipo", "kpi_type", "transaction_type"),
    "entity_name": ("entity_name", "vendor", "supplier_name", "proveedor", "customer", "cliente"),
    "amount": ("amount", "importe", "net_value", "monto", "value", "total"),
    "quantity": ("quantity", "qty", "cantidad", "units", "unidades"),
    "budget": ("budget", "presupuesto", "target", "plan_value"),
    "status": ("status", "estado", "result", "condition"),
    "cycle_days": ("cycle_days", "lead_time", "dias_ciclo", "processing_days"),
    "source_system": ("source_system", "system", "sistema", "origin", "fuente"),
}


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")


class SchemaMapper:
    def __init__(self, template_dir: str | Path | None = None) -> None:
        self.template_dir = Path(template_dir) if template_dir else None

    def suggest(self, columns: Iterable[str], threshold: float = 0.68) -> pd.DataFrame:
        suggestions: list[dict[str, object]] = []
        for original in columns:
            candidate = normalize_name(original)
            scores: list[tuple[float, str, str]] = []
            for canonical, aliases in ALIASES.items():
                for alias in aliases:
                    score = 1.0 if candidate == alias else SequenceMatcher(None, candidate, alias).ratio()
                    scores.append((score, canonical, alias))
            score, canonical, alias = max(scores)
            suggestions.append({
                "source_column": original,
                "canonical_column": canonical if score >= threshold else "",
                "confidence": round(score, 4),
                "matched_alias": alias,
                "review_status": "auto_approved" if score >= 0.92 else "human_review",
            })
        return pd.DataFrame(suggestions)

    def apply(self, frame: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
        cleaned = {source: target for source, target in mapping.items() if target}
        if len(set(cleaned.values())) != len(cleaned.values()):
            raise ValueError("Multiple source columns cannot map to the same canonical column")
        return frame.rename(columns=cleaned).copy()

    def auto_map(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        suggestions = self.suggest(frame.columns)
        mapping = dict(zip(suggestions["source_column"], suggestions["canonical_column"]))
        return self.apply(frame, mapping), suggestions

    def save_template(self, source_name: str, mapping: dict[str, str], approved_by: str) -> Path:
        if not self.template_dir:
            raise ValueError("template_dir is required to save templates")
        self.template_dir.mkdir(parents=True, exist_ok=True)
        path = self.template_dir / f"{normalize_name(source_name)}.json"
        payload = {"source": source_name, "mapping": mapping, "approved_by": approved_by}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

