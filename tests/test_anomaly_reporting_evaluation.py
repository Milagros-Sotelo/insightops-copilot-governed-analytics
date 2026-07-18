import unittest

import pandas as pd

from insightops.anomalies import detect_anomalies, robust_z_score
from insightops.audit import AuditLog
from insightops.copilot import DeterministicCopilot
from insightops.evaluation import evaluate
from insightops.reporting import create_monthly_report


def metric_history():
    rows = []
    for index, value in enumerate([100,102,98,101,99,103,100,45]):
        rows.append({"period":f"2025-{index+1:02d}","metric_id":"NET_SALES","value":value,"budget":100,"budget_variance":value/100-1,
                     "name":"Ventas netas","source":"vw_metric_monitoring","expected_min":60,"expected_max":140})
    return pd.DataFrame(rows)


class AnomalyReportingEvaluationTests(unittest.TestCase):
    def test_robust_anomaly_is_explainable(self):
        findings = detect_anomalies(metric_history())
        self.assertFalse(findings.empty)
        latest = findings.iloc[0]
        self.assertIn("robust_z_score", latest["method"])
        self.assertTrue(latest["explanation"])

    def test_report_requires_valid_human_transition(self):
        metrics = metric_history().assign(definition="x", formula="x", owner="Finance", frequency="monthly", improvement_direction="higher")
        anomalies = detect_anomalies(metric_history())
        quality = pd.DataFrame([{"quality_score":98}])
        report = create_monthly_report(metrics, anomalies, quality)
        audit = AuditLog()
        with self.assertRaises(ValueError):
            report.transition("Published", "reviewer", audit)
        report.transition("Under Review", "author", audit)
        report.transition("Approved", "manager", audit)
        self.assertEqual(report.approved_by, "manager")
        self.assertEqual(len(audit.events), 2)

    def test_offline_evaluation_scores_grounding(self):
        metrics = pd.concat([
            metric_history().assign(definition="x", formula="x", owner="Finance", frequency="monthly", improvement_direction="higher"),
            metric_history().assign(metric_id="GROSS_MARGIN", name="Margen bruto", value=lambda x:x["value"]/250, definition="x", formula="x", owner="Finance", frequency="monthly", improvement_direction="higher"),
            metric_history().assign(metric_id="EXPENSES", name="Gastos", definition="x", formula="x", owner="Finance", frequency="monthly", improvement_direction="lower"),
        ], ignore_index=True)
        anomalies = detect_anomalies(metrics)
        quality = pd.DataFrame([{"source_file":"x.csv","quality_score":96,"rows_rejected":2,"rows_received":100}])
        result = evaluate(DeterministicCopilot(metrics, anomalies, quality))
        self.assertGreaterEqual(result["score"].mean(), .8)


if __name__ == "__main__":
    unittest.main()

