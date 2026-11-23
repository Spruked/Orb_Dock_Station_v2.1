import unittest
from unittest.mock import patch

from app.services import diagnostics_snapshot


class DiagnosticsSnapshotTests(unittest.TestCase):
    def test_intelligence_metrics_are_projected_from_communication(self):
        communication = {
            "intelligence.active_model": diagnostics_snapshot.metric("nvidia/model", "communication"),
            "intelligence.provider": diagnostics_snapshot.metric("nvidia", "communication"),
            "intelligence.local_or_remote": diagnostics_snapshot.metric("remote", "communication"),
            "intelligence.response_latency": diagnostics_snapshot.metric(125, "communication.intelligence"),
            "intelligence.tokens_per_second": diagnostics_snapshot.metric(18.4, "communication.intelligence"),
            "intelligence.failed_calls": diagnostics_snapshot.metric(2, "communication.intelligence"),
            "intelligence.timed_out_calls": diagnostics_snapshot.metric(1, "communication.intelligence"),
            "intelligence.remote_enabled": diagnostics_snapshot.metric(True, "communication"),
        }

        def producer(pair):
            name, _port = pair
            if name == "communication":
                return name, communication
            return name, {"running": diagnostics_snapshot.metric(True, name)}

        with patch.object(diagnostics_snapshot, "poll", side_effect=producer):
            result = diagnostics_snapshot.snapshot()

        intelligence = result["sections"]["Intelligence and models"]
        self.assertEqual(intelligence["active_model"]["value"], "nvidia/model")
        self.assertEqual(intelligence["response_latency"]["value"], 125)
        self.assertEqual(intelligence["tokens_per_second"]["value"], 18.4)
        self.assertEqual(intelligence["failed_calls"]["value"], 2)
        self.assertEqual(intelligence["timed_out_calls"]["value"], 1)
        self.assertEqual(intelligence["remote_enabled"]["value"], True)


if __name__ == "__main__":
    unittest.main()
