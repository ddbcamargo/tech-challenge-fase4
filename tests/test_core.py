import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fase4.domain.anomalies import (Anomaly, detect_pose_outliers,
                                    detect_prescription_changes, detect_vital_anomalies,
                                    fusion_alert)
from fase4.infrastructure.database import (add_alert, connect, initialize, list_alerts,
                                           list_patients, list_vitals)
from fase4.infrastructure.datasets.audioset import read_segments
from fase4.infrastructure.datasets.physionet import import_psv, read_challenge2019_psv
from fase4.infrastructure.seed import seed_example_prescriptions, seed_patients
from fase4.infrastructure.pose import angle_degrees


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.con = connect(":memory:")
        initialize(self.con)

    def tearDown(self):
        self.con.close()

    def test_new_patients_are_synthetic_and_seed_is_idempotent(self):
        self.assertEqual(seed_patients(self.con), 25)
        self.assertEqual(seed_patients(self.con), 0)
        patients = list_patients(self.con)
        self.assertEqual(len(patients), 25)
        self.assertEqual(patients[0]["patient_id"], "TC4-P001")
        self.assertIn("Ficticia", patients[0]["name"])

    def test_prescriptions_trigger_administrative_review(self):
        seed_patients(self.con, 1)
        seed_example_prescriptions(self.con)
        seed_example_prescriptions(self.con)
        rows = [dict(row) for row in self.con.execute(
            "SELECT medication, dose, unit, frequency, valid_from FROM prescriptions")]
        self.assertEqual(len(rows), 2)
        events = detect_prescription_changes("TC4-P001", rows)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].modality, "prescription")

    def test_duplicate_alert_is_ignored(self):
        seed_patients(self.con, 1)
        args = ("TC4-P001", "2026-01-01T00:00:00+00:00", "vitals", "warning",
                "VITAL_HR", "Desvio estatistico", {"value": 150})
        add_alert(self.con, *args)
        add_alert(self.con, *args)
        self.assertEqual(len(list_alerts(self.con)), 1)

    def test_physionet_import_and_missing_values(self):
        seed_patients(self.con, 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p000001.psv"
            path.write_text("HR|O2Sat|SBP|DBP|Resp|Temp\n80|98|120|80|16|NaN\n81|NaN|121|81|17|36.5\n",
                            encoding="utf-8")
            records = read_challenge2019_psv(path)
            self.assertIsNone(records[0]["Temp"])
            self.assertEqual(import_psv(self.con, path, "TC4-P001"), 10)
            self.assertEqual(import_psv(self.con, path, "TC4-P001"), 0)
            self.assertEqual(len(list_vitals(self.con, "TC4-P001")), 10)

    def test_unrecognizable_dataset_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.psv"
            path.write_text("foo|bar\na|b\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_challenge2019_psv(path)


class DatasetTests(unittest.TestCase):
    def test_audioset_index_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "eval_segments.csv"
            path.write_text('# header\nabc123def45, 0.000, 10.000, "/m/111,/m/222"\n',
                            encoding="utf-8")
            segments = read_segments(path)
            self.assertEqual(len(segments), 1)
            self.assertEqual(segments[0].label_ids, ("/m/111", "/m/222"))


class AnomalyTests(unittest.TestCase):
    def test_robust_vitals_alert(self):
        values = [80, 80, 81, 79, 80, 130]
        records = [{"observed_at": f"2026-01-01T{i:02}:00:00+00:00",
                    "metric": "HR", "value": value}
                   for i, value in enumerate(values)]
        alerts = detect_vital_anomalies("TC4-P001", records)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].code, "VITAL_HR")

    def test_pose_angles_and_outlier(self):
        self.assertAlmostEqual(angle_degrees((0, 1), (0, 0), (1, 0)), 90)
        samples = [{"observed_at": f"2026-01-01T00:00:{i:02}+00:00",
                    "left_knee": value}
                   for i, value in enumerate([90, 91, 89, 90, 90, 140])]
        self.assertEqual(len(detect_pose_outliers("TC4-P001", samples)), 1)

    def test_fusion_requires_distinct_modalities_same_time_window(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        first = Anomaly("TC4-P001", now.isoformat(), "video", "warning", "V1", "", {})
        close = Anomaly("TC4-P001", (now + timedelta(minutes=4)).isoformat(),
                        "audio", "warning", "A1", "", {})
        far = Anomaly("TC4-P001", (now + timedelta(days=1)).isoformat(),
                      "audio", "warning", "A2", "", {})
        self.assertIsNotNone(fusion_alert("TC4-P001", [first, close]))
        self.assertIsNone(fusion_alert("TC4-P001", [first, far]))
        self.assertIsNone(fusion_alert("TC4-P002", [first, close]))


if __name__ == "__main__":
    unittest.main()

