"""Replay causal, isolado por origem, com revisão persistente de alertas."""

import tempfile
import unittest
from pathlib import Path

from fase4.container import build_application
from fase4.domain.replay import build_replay_frame, sources_for_replay
from fase4.infrastructure.database import add_vital, connect


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "fase4.sqlite3"
        self.app = build_application(self.db_path)
        self.app.bootstrap()
        with connect(self.db_path) as con:
            for hour, heart_rate in enumerate([80, 80, 80, 80, 80, 165, 82]):
                stamp = f"2026-01-01T{hour:02}:00:00+00:00"
                add_vital(con, "TC4-P001", stamp, "HR", heart_rate, "source-A")
                add_vital(con, "TC4-P001", stamp, "O2Sat", 98, "source-A")
            # A segunda série não pode se somar ao histórico da primeira.
            add_vital(con, "TC4-P001", "2026-01-01T00:00:00+00:00", "HR", 215, "source-B")

    def tearDown(self):
        self.temp.cleanup()

    def test_replay_shows_only_past_data_and_does_not_write_on_preview(self):
        sources = self.app.replay_sources("TC4-P001")
        self.assertEqual([(item["source"], item["hours"]) for item in sources],
                         [("source-A", 7), ("source-B", 1)])

        initial = self.app.replay_preview("TC4-P001", "source-A")
        self.assertEqual(initial.position, 0)
        self.assertEqual(initial.history, [])
        self.assertIsNone(initial.observed_at)

        previous = self.app.replay_preview("TC4-P001", "source-A", 5)
        self.assertEqual(len(previous.history), 10)
        self.assertEqual(previous.new_events, [])
        self.assertEqual(self.app.alerts("TC4-P001"), [])

        future = self.app.replay_preview("TC4-P001", "source-A", 6)
        self.assertEqual(len(future.new_events), 1)
        self.assertEqual(future.current_values["HR"], 165)
        self.assertEqual(self.app.alerts("TC4-P001"), [], "prévia não grava alertas")

    def test_advance_persists_one_event_only_and_review_is_idempotent(self):
        for step in range(6):
            result = self.app.replay_next("TC4-P001", "source-A", step)
        self.assertEqual(result.position, 6)
        self.assertEqual(len(result.new_events), 1)
        alerts = self.app.alerts("TC4-P001")
        self.assertEqual(len(alerts), 1)
        alert_id = alerts[0]["id"]
        self.assertEqual(alerts[0]["status"], "pending_review")

        # Repetir a hora não duplica o evento.
        self.app.replay_next("TC4-P001", "source-A", 5)
        self.assertEqual(len(self.app.alerts("TC4-P001")), 1)

        self.assertFalse(self.app.review_alert(alert_id, "TC4-P002", "reviewed"))
        with self.assertRaises(ValueError):
            self.app.review_alert(alert_id, "TC4-P001", "pending_review")
        self.assertTrue(self.app.review_alert(alert_id, "TC4-P001", "reviewed"))
        self.assertFalse(self.app.review_alert(alert_id, "TC4-P001", "dismissed"))
        self.assertEqual(self.app.alerts("TC4-P001")[0]["status"], "reviewed")

    def test_source_isolation_and_end_of_series(self):
        isolated = self.app.replay_preview("TC4-P001", "source-B", 1)
        self.assertEqual(len(isolated.history), 1)
        self.assertEqual(isolated.current_values, {"HR": 215})
        self.assertEqual(isolated.events, [])
        with self.assertRaisesRegex(ValueError, "última observação"):
            self.app.replay_next("TC4-P001", "source-B", 1)
        with self.assertRaises(ValueError):
            self.app.replay_preview("TC4-P001", "unknown", 0)
        with self.assertRaises(ValueError):
            self.app.replay_preview("TC4-P001", "source-A", 8)

    def test_pure_domain_functions(self):
        rows = [{"observed_at": "2026-01-01T00:00:00+00:00", "source": "S",
                 "metric": "HR", "value": 80}]
        self.assertEqual(sources_for_replay(rows)[0]["measurements"], 1)
        self.assertEqual(build_replay_frame("P", rows, "S", 1).total_steps, 1)


if __name__ == "__main__":
    unittest.main()
