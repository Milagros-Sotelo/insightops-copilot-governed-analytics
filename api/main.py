"""FastAPI surface for ingestion, monitoring, Copilot and report approval."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from insightops.audit import AuditEvent, AuditLog
from insightops.copilot import DeterministicCopilot
from insightops.intake import IntakeRegistry
from insightops.mapping import SchemaMapper
from insightops.quality import QualityEngine
from insightops.reporting import ReportDraft


DATA_DIR = Path(os.getenv("INSIGHTOPS_DATA_DIR", "data/demo"))
MARTS = DATA_DIR / "marts"
app = FastAPI(title="InsightOps Copilot API", version="1.0.0", description="Governed analytics automation API for Asteria Services")
audit = AuditLog(DATA_DIR / "api_audit.jsonl")
registry = IntakeRegistry()


class QuestionRequest(BaseModel):
    question: str = Field(min_length=4, max_length=1000)
    user: str = Field(default="api.user@asteria.example", max_length=200)


class ReportDecision(BaseModel):
    decision: Literal["approve", "reject"]
    user: str = Field(min_length=3, max_length=200)
    comment: str = Field(default="", max_length=1000)


def read_mart(name: str) -> pd.DataFrame:
    path = MARTS / f"{name}.csv"
    if not path.exists():
        raise HTTPException(503, "Demo marts are not available. Run the pipeline first.")
    return pd.read_csv(path)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "deterministic"}


@app.post("/files")
async def upload_files(files: list[UploadFile] = File(...), user: str = "api.user@asteria.example") -> dict[str, object]:
    results = []
    for item in files:
        data = await item.read()
        try:
            metadata, frame = registry.read(item.filename or "upload.csv", data)
            mapped, suggestions = SchemaMapper().auto_map(frame)
            outcome = QualityEngine().validate(mapped)
            results.append({**metadata.to_dict(), "rows": len(frame), "accepted": len(outcome.accepted), "rejected": len(outcome.rejected), "quality_score": outcome.quality_score, "mapping": suggestions.to_dict("records")})
            audit.record(AuditEvent("api_file_validated", user, "source_file", metadata.file_name, {"hash": metadata.file_hash, "quality_score": outcome.quality_score}))
        except ValueError as error:
            results.append({"file_name": item.filename, "status": "rejected", "error": str(error)})
    return {"files": results}


@app.get("/runs")
def runs(limit: int = Query(50, ge=1, le=200)) -> list[dict[str, object]]:
    return read_mart("ingestion_runs").sort_values("started_at", ascending=False).head(limit).to_dict("records")


@app.get("/quality")
def quality(limit: int = Query(50, ge=1, le=200)) -> list[dict[str, object]]:
    return read_mart("quality_summary").sort_values("quality_score").head(limit).to_dict("records")


@app.get("/metrics")
def metrics(metric_id: str | None = None, period: str | None = None) -> list[dict[str, object]]:
    frame = read_mart("metric_results")
    if metric_id:
        frame = frame.loc[frame["metric_id"].eq(metric_id)]
    if period:
        frame = frame.loc[frame["period"].eq(period)]
    return frame.tail(200).to_dict("records")


@app.get("/anomalies")
def anomalies(severity: str | None = None, status: str = "open") -> list[dict[str, object]]:
    frame = read_mart("anomaly_results")
    frame = frame.loc[frame["review_status"].eq(status)]
    if severity:
        frame = frame.loc[frame["severity"].eq(severity)]
    return frame.head(200).to_dict("records")


@app.post("/copilot/questions")
def ask_copilot(request: QuestionRequest) -> dict[str, object]:
    engine = DeterministicCopilot(read_mart("metric_results"), read_mart("anomaly_results"), read_mart("quality_summary"), audit)
    try:
        return engine.answer(request.question, request.user).to_dict()
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@app.get("/reports/current")
def current_report() -> dict[str, object]:
    path = DATA_DIR / "report_draft.json"
    if not path.exists():
        raise HTTPException(404, "No report draft is available")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/reports/{report_id}/decision")
def decide_report(report_id: str, request: ReportDecision) -> dict[str, object]:
    payload = current_report()
    if payload["report_id"] != report_id:
        raise HTTPException(404, "Report not found")
    if payload["status"] not in {"Draft", "Under Review"}:
        raise HTTPException(409, "Report already has a terminal review decision")
    payload["status"] = "Approved" if request.decision == "approve" else "Rejected"
    payload["approved_by"] = request.user if request.decision == "approve" else None
    payload["review_comment"] = request.comment
    (DATA_DIR / "report_draft.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    audit.record(AuditEvent("report_decision", request.user, "report", report_id, {"decision": request.decision, "comment": request.comment}))
    return payload

