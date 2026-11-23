"""Numeric-equivalence checks used by the embedded-to-server migration."""
from types import SimpleNamespace
import unittest

from deployment.qdrant.migrate_local_to_server import points_equivalent


class QdrantMigrationComparisonTest(unittest.TestCase):
    def test_sub_tolerance_vector_drift_is_accepted(self):
        source = SimpleNamespace(id="point-1", payload={"title": "Law"}, vector=[0.25, 0.75])
        target = SimpleNamespace(id="point-1", payload={"title": "Law"},
                                 vector=[0.250000001, 0.749999999])
        self.assertTrue(points_equivalent(source, target, vector_atol=1e-7))

    def test_vector_drift_above_tolerance_is_rejected(self):
        source = SimpleNamespace(id="point-1", payload={}, vector=[0.25, 0.75])
        target = SimpleNamespace(id="point-1", payload={}, vector=[0.2500002, 0.75])
        self.assertFalse(points_equivalent(source, target, vector_atol=1e-7))

    def test_id_and_payload_must_match_exactly(self):
        source = SimpleNamespace(id="point-1", payload={"title": "Law"}, vector=[0.25, 0.75])
        wrong_id = SimpleNamespace(id="point-2", payload={"title": "Law"}, vector=[0.25, 0.75])
        wrong_payload = SimpleNamespace(id="point-1", payload={"title": "Different"},
                                        vector=[0.25, 0.75])
        self.assertFalse(points_equivalent(source, wrong_id))
        self.assertFalse(points_equivalent(source, wrong_payload))


if __name__ == "__main__":
    unittest.main(verbosity=2)
