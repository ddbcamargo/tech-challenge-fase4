"""Casos de uso testados com substitutos das integrações externas."""

import tempfile
import unittest
from pathlib import Path

from fase4.application.service import ApplicationService
from fase4.container import build_application
from fase4.infrastructure.adapters import GoogleAudioSet, SqlitePatientStore
from fase4.interfaces.cli import doctor


class FakeSpeech:
    def transcribe(self, path):
        return "Estou com falta de ar."

    def analyze(self, text):
        return {"sentiment": "neutral", "provider": "fake-for-test-only"}


class FakePose:
    def analyze(self, path):
        return [{"observed_at": f"2026-01-01T00:00:{n:02}+00:00",
                 "left_knee": value}
                for n, value in enumerate([90, 90, 89, 91, 90, 142])]


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "new_fase4.sqlite3"
        self.app = ApplicationService(SqlitePatientStore(self.path), FakeSpeech(),
                                      FakePose(), GoogleAudioSet())

    def tearDown(self):
        self.temp.cleanup()

    def test_bootstrap_and_one_application_for_all_interfaces(self):
        self.assertEqual(self.app.bootstrap(), 25)
        self.assertEqual(self.app.bootstrap(), 0)
        self.assertEqual(len(self.app.patients()), 25)
        self.assertEqual(len(self.app.scan_prescriptions("TC4-P001")), 1)
        self.assertEqual(len(self.app.alerts("TC4-P001")), 1)
        self.assertEqual(len(build_application(self.path).patients()), 25)

    def test_audio_and_video_use_cases_without_real_cloud_calls(self):
        self.app.bootstrap()
        audio = self.app.process_audio("TC4-P001", "ignored.wav", "encenado.wav")
        self.assertIn("falta de ar", audio["transcript"])
        video = self.app.process_video("TC4-P001", "ignored.mp4", "fisioterapia.mp4")
        self.assertEqual(video["alert_count"], 1)
        codes = {item["code"] for item in self.app.alerts("TC4-P001")}
        self.assertIn("AUDIO_TERMS", codes)
        self.assertIn("POSE_LEFT_KNEE", codes)

    def test_doctor_reports_configuration_without_secrets(self):
        status = doctor()
        self.assertIn("azure_speech_configured", status)
        self.assertNotIn("AZURE_SPEECH_KEY", status)


if __name__ == "__main__":
    unittest.main()
