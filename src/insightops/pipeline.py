"""End-to-end orchestrator for the InsightOps governed analytics flow."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

import pandas as pd

from .anomalies import detect_anomalies
from .audit import AuditEvent, AuditLog
from .copilot import DeterministicCopilot
from .database import load_sqlite
from .generator import DemoProfile, write_demo_files
from .intake import IntakeRegistry
from .mapping import SchemaMapper
from .metrics import calculate_metrics, metric_catalog
from .models import IngestionRun
from .quality import QualityEngine
from .reporting import create_monthly_report, save_report


def run_pipeline(output_dir: str | Path = "data/demo", seed: int = 20260717) -> dict[str, object]:
    root = Path(output_dir)
    raw_dir, marts_dir, rejected_dir = root / "raw", root / "marts", root / "rejected"
    for directory in (raw_dir, marts_dir, rejected_dir):
        directory.mkdir(parents=True, exist_ok=True)
    source_paths = write_demo_files(raw_dir, DemoProfile(seed=seed))
    registry, mapper, quality_engine = IntakeRegistry(), SchemaMapper(root / "templates"), QualityEngine()
    audit_path = root / "audit_events.jsonl"
    audit_path.unlink(missing_ok=True)
    audit = AuditLog(audit_path)
    accepted_frames: list[pd.DataFrame] = []
    run_rows: list[dict[str, object]] = []
    source_rows: list[dict[str, object]] = []
    mapping_rows: list[pd.DataFrame] = []
    rule_rows: list[pd.DataFrame] = []
    for path in sorted(source_paths):
        started = time.perf_counter()
        metadata, incoming = registry.read_path(path)
        source_rows.append(metadata.to_dict())
        run = IngestionRun(str(uuid.uuid4()), metadata.file_name, metadata.uploaded_by, rows_received=len(incoming))
        if metadata.status == "duplicate":
            run.status = "duplicate_skipped"
            run.completed_at = pd.Timestamp.now(tz="UTC").isoformat()
            run.processing_time_ms = int((time.perf_counter() - started) * 1000)
            run_rows.append(run.to_dict())
            audit.record(AuditEvent("duplicate_file_skipped", run.user, "source_file", metadata.file_name, {"duplicate_of": metadata.duplicate_of, "hash": metadata.file_hash}))
            continue
        canonical, suggestions = mapper.auto_map(incoming)
        suggestions.insert(0, "source_file", metadata.file_name)
        mapping_rows.append(suggestions)
        outcome = quality_engine.validate(canonical)
        accepted = outcome.accepted.copy()
        accepted["source_file"] = metadata.file_name
        accepted["run_id"] = run.run_id
        accepted_frames.append(accepted)
        if not outcome.rejected.empty:
            outcome.rejected.assign(source_file=metadata.file_name, run_id=run.run_id).to_csv(rejected_dir / f"{path.stem}_rejected.csv", index=False)
        rules = outcome.rule_results.copy()
        rules.insert(0, "source_file", metadata.file_name)
        rules["run_id"] = run.run_id
        rule_rows.append(rules)
        run.rows_accepted, run.rows_rejected = len(outcome.accepted), len(outcome.rejected)
        run.quality_score, run.status = outcome.quality_score, "completed"
        run.completed_at = pd.Timestamp.now(tz="UTC").isoformat()
        run.processing_time_ms = int((time.perf_counter() - started) * 1000)
        run_rows.append(run.to_dict())
        audit.record(AuditEvent("ingestion_completed", run.user, "ingestion_run", run.run_id, {"source_file": metadata.file_name, "accepted": run.rows_accepted, "rejected": run.rows_rejected, "quality_score": run.quality_score}))
    accepted = pd.concat(accepted_frames, ignore_index=True)
    runs = pd.DataFrame(run_rows)
    sources = pd.DataFrame(source_rows)
    mappings = pd.concat(mapping_rows, ignore_index=True)
    quality_results = pd.concat(rule_rows, ignore_index=True)
    metrics = calculate_metrics(accepted)
    anomalies = detect_anomalies(metrics)
    quality_summary = runs[["run_id", "source_file", "rows_received", "rows_accepted", "rows_rejected", "quality_score", "status", "processing_time_ms"]].copy()
    report = create_monthly_report(metrics, anomalies, quality_summary)
    save_report(report, root / "report_draft.json")
    tables = {
        "ingestion_runs": runs, "source_files": sources, "schema_mappings": mappings,
        "quality_results": quality_results, "accepted_records": accepted,
        "metric_definitions": metric_catalog(), "metric_results": metrics,
        "anomaly_results": anomalies, "report_drafts": pd.DataFrame([report.to_dict()]),
        "audit_events": pd.DataFrame(audit.events),
    }
    for name, frame in tables.items():
        if name not in {"accepted_records", "audit_events"}:
            frame.to_csv(marts_dir / f"{name}.csv", index=False)
    metrics.to_csv(marts_dir / "metric_results.csv", index=False)
    anomalies.to_csv(marts_dir / "anomaly_results.csv", index=False)
    quality_summary.to_csv(marts_dir / "quality_summary.csv", index=False)
    load_sqlite(root / "insightops_demo.db", tables)
    copilot = DeterministicCopilot(metrics, anomalies, quality_summary, audit)
    sample_answer = copilot.answer("¿Qué KPI se desviaron este mes?", actor="pipeline.validation")
    manifest = {
        "project": "InsightOps Copilot", "company": "Asteria Services", "seed": seed,
        "months": 24, "source_files": len(sources), "runs": len(runs),
        "rows_received": int(runs["rows_received"].sum()), "rows_accepted": int(runs["rows_accepted"].sum()),
        "rows_rejected": int(runs["rows_rejected"].sum()), "duplicate_files": int(sources["status"].eq("duplicate").sum()),
        "mean_quality_score": round(float(runs.loc[runs["status"].eq("completed"), "quality_score"].mean()), 2),
        "metric_results": len(metrics), "anomalies": len(anomalies), "latest_period": str(metrics["period"].max()),
        "report_status": report.status, "copilot_mode": "deterministic", "sample_answer": sample_answer.to_dict(),
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the InsightOps Copilot pipeline")
    parser.add_argument("--output", default="data/demo")
    parser.add_argument("--seed", default=20260717, type=int)
    args = parser.parse_args()
    manifest = run_pipeline(args.output, args.seed)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
