import tempfile
import unittest
from pathlib import Path

import pandas as pd

from insightops.intake import IntakeRegistry, detect_encoding, detect_separator, file_hash
from insightops.mapping import SchemaMapper


class IntakeMappingTests(unittest.TestCase):
    def test_hash_is_stable_and_duplicates_are_detected(self):
        data = b"fecha;importe\n2026-01-01;100\n"
        self.assertEqual(file_hash(data), file_hash(data))
        registry = IntakeRegistry()
        first = registry.inspect("first.csv", data)
        second = registry.inspect("copy.csv", data)
        self.assertEqual(first.status, "received")
        self.assertEqual(second.status, "duplicate")
        self.assertEqual(second.duplicate_of, "first.csv")

    def test_encoding_and_separator_detection(self):
        data = "fecha;importe\n2026-01-01;120\n".encode("utf-8")
        self.assertIn(detect_encoding(data), {"utf-8-sig", "utf-8"})
        self.assertEqual(detect_separator(data, "utf-8"), ";")

    def test_schema_mapping_supports_synonyms(self):
        frame = pd.DataFrame({"fecha": ["2026-01-01"], "net_value": [100], "proveedor": ["Atlas"]})
        mapped, suggestions = SchemaMapper().auto_map(frame)
        self.assertIn("transaction_date", mapped.columns)
        self.assertIn("amount", mapped.columns)
        self.assertIn("entity_name", mapped.columns)
        self.assertTrue((suggestions["confidence"] >= .92).all())

    def test_duplicate_canonical_targets_are_blocked(self):
        with self.assertRaises(ValueError):
            SchemaMapper().apply(pd.DataFrame({"a": [1], "b": [2]}), {"a": "amount", "b": "amount"})


if __name__ == "__main__":
    unittest.main()

