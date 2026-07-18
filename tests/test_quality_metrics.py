import unittest

import pandas as pd

from insightops.metrics import calculate_metrics, metric_catalog
from insightops.quality import QualityEngine


def sample_frame():
    return pd.DataFrame([
        {"record_id":"A1","transaction_date":"2026-01-05","area":"Ventas","metric_type":"sales","entity_name":"C1","amount":1000,"quantity":2,"budget":900,"status":"approved","cycle_days":5,"source_system":"CRM"},
        {"record_id":"A2","transaction_date":"2026-01-06","area":"Ventas","metric_type":"margin_input","entity_name":"C1","amount":600,"quantity":1,"budget":650,"status":"on_time","cycle_days":4,"source_system":"CRM"},
        {"record_id":"A3","transaction_date":"2026-01-07","area":"Finanzas","metric_type":"expense","entity_name":"V1","amount":300,"quantity":1,"budget":250,"status":"late","cycle_days":7,"source_system":"ERP"},
    ])


class QualityMetricTests(unittest.TestCase):
    def test_quality_rejects_negative_future_and_duplicate(self):
        frame = pd.concat([sample_frame(), sample_frame().iloc[[0]]], ignore_index=True)
        frame.loc[1, "amount"] = -10
        frame.loc[2, "transaction_date"] = "2027-01-01"
        outcome = QualityEngine().validate(frame)
        self.assertEqual(len(outcome.accepted), 1)
        self.assertEqual(len(outcome.rejected), 3)
        self.assertLess(outcome.quality_score, 100)
        self.assertIn("rejection_reason", outcome.rejected.columns)

    def test_quality_score_has_five_dimensions(self):
        outcome = QualityEngine().validate(sample_frame())
        self.assertEqual(set(outcome.dimensions), {"completeness","validity","uniqueness","consistency","timeliness"})
        self.assertEqual(outcome.quality_score, 100)

    def test_metric_catalog_is_governed(self):
        catalog = metric_catalog()
        self.assertEqual(len(catalog), 10)
        self.assertFalse(catalog[["metric_id","definition","formula","owner","source"]].isna().any().any())

    def test_sales_margin_and_expense_calculation(self):
        metrics = calculate_metrics(sample_frame()).set_index("metric_id")
        self.assertEqual(metrics.loc["NET_SALES", "value"], 1000)
        self.assertAlmostEqual(metrics.loc["GROSS_MARGIN", "value"], .4)
        self.assertEqual(metrics.loc["EXPENSES", "value"], 300)


if __name__ == "__main__":
    unittest.main()

