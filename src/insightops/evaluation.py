"""Offline evaluation suite for grounded deterministic Copilot behavior."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .audit import AuditLog
from .copilot import DeterministicCopilot


DEFAULT_CASES = (
    {"id": "E01", "question": "¿Qué KPI se desviaron este mes?", "expected_sufficient": True, "required_source": "vw_anomaly_center"},
    {"id": "E02", "question": "¿Por qué bajó el margen?", "expected_sufficient": True, "required_source": "vw_metric_monitoring"},
    {"id": "E03", "question": "¿Qué archivos tuvieron peor calidad?", "expected_sufficient": True, "required_source": "vw_quality_summary"},
    {"id": "E04", "question": "¿Qué proveedores concentran mayor gasto?", "expected_sufficient": False, "required_source": ""},
    {"id": "E05", "question": "¿Cuál será el tipo de cambio del mes próximo?", "expected_sufficient": False, "required_source": ""},
)


def evaluate(copilot: DeterministicCopilot) -> pd.DataFrame:
    results: list[dict[str, object]] = []
    for case in DEFAULT_CASES:
        answer = copilot.answer(str(case["question"]), actor="evaluation.runner")
        sufficient_match = answer.sufficient_data == case["expected_sufficient"]
        source_match = not case["required_source"] or case["required_source"] in answer.sources
        no_unsupported_number = answer.sufficient_data or not any(char.isdigit() for char in answer.answer)
        has_period = bool(answer.period)
        secure_sql = not answer.sql or answer.sql.lower().startswith(("select", "with"))
        score = sum((sufficient_match, source_match, no_unsupported_number, has_period, secure_sql)) / 5
        results.append({
            "case_id": case["id"], "question": case["question"], "sufficient_match": sufficient_match,
            "source_fidelity": source_match, "unsupported_numeric_claims": not no_unsupported_number,
            "period_present": has_period, "security_compliant": secure_sql, "score": score,
        })
    return pd.DataFrame(results)


def run_evaluation(data_dir: str | Path, output: str | Path) -> pd.DataFrame:
    base = Path(data_dir)
    copilot = DeterministicCopilot(
        pd.read_csv(base / "metric_results.csv"),
        pd.read_csv(base / "anomaly_results.csv"),
        pd.read_csv(base / "quality_summary.csv"),
        AuditLog(),
    )
    result = evaluate(copilot)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"summary_score": float(result["score"].mean()), "cases": result.to_dict("records")}, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate InsightOps Copilot")
    parser.add_argument("--data-dir", default="data/demo/marts")
    parser.add_argument("--output", default="reports/copilot_evaluation.json")
    args = parser.parse_args()
    result = run_evaluation(args.data_dir, args.output)
    print(f"Evaluation score: {result['score'].mean():.1%} ({len(result)} cases)")


if __name__ == "__main__":
    main()

