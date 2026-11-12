"""Testes do fluxo oficial com downloads simulados, sem rede externa."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fase4.container import build_application
from fase4.domain.anomalies import detect_vital_anomalies
from fase4.infrastructure.database import connect, initialize, list_vitals
from fase4.infrastructure.datasets.catalog import OFFICIAL_FILES
from fase4.infrastructure.datasets.physionet import import_psv
from fase4.infrastructure.seed import seed_patients


PSV = b"HR|O2Sat|SBP|DBP|Resp|Temp\n80|98|120|80|16|NaN\n81|NaN|121|81|17|36.5\n"
SEGMENTS = b'# YTID, start_seconds, end_seconds, positive_labels\nabc123def45, 0.0, 10.0, "/m/09x0r"\n'
LABELS = b'index,mid,display_name\n0,/m/09x0r,Speech\n1,/t/dd00001,Baby laughter\n'


class OfficialDatasetTests(unittest.TestCase):
    def test_prepare_validate_and_preview_without_network(self):
        content = {"p100679.psv": PSV, "eval_segments.csv": SEGMENTS,
                   "balanced_train_segments.csv": SEGMENTS,
                   "class_labels_indices.csv": LABELS}
        urls = {spec.url: content[spec.name] for spec in OFFICIAL_FILES}

        def fake_urlopen(url, timeout):
            self.assertEqual(timeout, 30)
            return io.BytesIO(urls[url])

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "official"
            app = build_application(Path(directory) / "demo.sqlite3")
            with patch("fase4.infrastructure.datasets.catalog.urlopen", side_effect=fake_urlopen) as get:
                first = app.prepare_datasets(destination)
                self.assertEqual(get.call_count, 4)
                second = app.prepare_datasets(destination)
                self.assertEqual(get.call_count, 4, "download idempotente")

            self.assertTrue(first["ready"])
            self.assertTrue(second["ready"])
            self.assertEqual(first["files"]["p100679.psv"]["hourly_rows"], 2)
            self.assertEqual(first["files"]["eval_segments.csv"]["segments_with_speech_labels"], 1)
            names = app.audioset_preview(destination / "eval_segments.csv", 1)[0]["label_names"]
            self.assertEqual(names, ["Speech"])
            self.assertEqual(len(app.audioset_speech_examples(destination / "eval_segments.csv", 5)), 1)
            self.assertEqual(app.validate_datasets(destination)["files"]["class_labels_indices.csv"]["classes"], 2)

            (destination / "eval_segments.csv").write_text("arquivo corrompido", encoding="utf-8")
            self.assertFalse(app.validate_datasets(destination)["ready"])
            with self.assertRaises(ValueError):
                app.prepare_datasets(destination)

    def test_existing_file_without_manifest_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            (destination / "p100679.psv").write_bytes(PSV)
            with self.assertRaisesRegex(ValueError, "sem procedência"):
                build_application().prepare_datasets(destination)

    def test_different_psv_sources_do_not_collide_or_share_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path_a, path_b = root / "sourceA.psv", root / "sourceB.psv"
            path_a.write_bytes(PSV)
            path_b.write_bytes(PSV.replace(b"80|98", b"91|98"))
            with connect(root / "records.sqlite3") as con:
                initialize(con)
                seed_patients(con, 1)
                self.assertEqual(import_psv(con, path_a, "TC4-P001"), 10)
                self.assertEqual(import_psv(con, path_b, "TC4-P001"), 10)
                self.assertEqual(import_psv(con, path_a, "TC4-P001"), 0)
                self.assertEqual(len({row["source"] for row in list_vitals(con, "TC4-P001")}), 2)

        records = [
            {"observed_at": f"2026-01-01T{i:02}:00:00+00:00", "metric": "HR",
             "value": 80, "source": "A"} for i in range(6)
        ]
        records += [{"observed_at": "2026-01-01T06:00:00+00:00", "metric": "HR",
                     "value": 180, "source": "B"}]
        self.assertEqual(detect_vital_anomalies("TC4-P001", records), [])


if __name__ == "__main__":
    unittest.main()
