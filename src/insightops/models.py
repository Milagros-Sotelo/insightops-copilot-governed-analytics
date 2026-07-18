"""Typed domain models shared by pipeline modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SourceFile:
    file_name: str
    file_hash: str
    size_bytes: int
    encoding: str
    separator: str
    sheet_names: tuple[str, ...] = ()
    uploaded_by: str = "demo.user@asteria.example"
    uploaded_at: str = field(default_factory=utc_now)
    status: str = "received"
    duplicate_of: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IngestionRun:
    run_id: str
    source_file: str
    user: str
    started_at: str = field(default_factory=utc_now)
    completed_at: str | None = None
    processing_time_ms: int = 0
    rows_received: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    quality_score: float = 0.0
    status: str = "received"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CopilotAnswer:
    question: str
    answer: str
    sql: str
    sources: tuple[str, ...]
    metrics: tuple[str, ...]
    period: str
    facts: tuple[str, ...]
    hypotheses: tuple[str, ...]
    warning: str
    sufficient_data: bool

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sources"] = list(self.sources)
        data["metrics"] = list(self.metrics)
        data["facts"] = list(self.facts)
        data["hypotheses"] = list(self.hypotheses)
        return data

