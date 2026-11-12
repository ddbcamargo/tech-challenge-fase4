"""Ensaios locais do ML acústico v0.8 (nenhum serviço Azure é chamado)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from fase4.application.service import ApplicationService
from fase4.domain.voice import FEATURE_NAMES, feature_vector, label_outlier
from fase4.infrastructure.adapters import GoogleAudioSet, LocalWavInspector, SqlitePatientStore
from fase4.infrastructure.voice_features import features_from_wav
from fase4.infrastructure.voice_model import (
    IsolationForestVoiceModel, make_synthetic_signal, write_pcm16,
)


class TestVoiceModel(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model = IsolationForestVoiceModel(self.root / "models" / "voice.joblib")

    def test_train_demo_score_and_reload(self):
        self.assertFalse(self.model.status()["ready"])
        state = self.model.train_demo()
        self.assertTrue(state["ready"])
        self.assertEqual(state["reference_count"], 48)
        self.assertEqual(state["mode"], "synthetic_demo")
        demo = self.model.prepare_demo(self.root / "demo")
        good = self.model.analyze(demo["reference"])
        altered = self.model.analyze(demo["altered"])
        self.assertEqual(good["prediction"], "inlier")
        self.assertEqual(altered["prediction"], "outlier")
        self.assertIn("CLIPPING", altered["quality_flags"])
        self.assertEqual(altered["ml_prediction"], "inlier")  # aviso não falsifica ML
        self.assertFalse(good["clinical_assessment"])
        self.assertEqual(set(good["features"]), set(FEATURE_NAMES))
        self.assertTrue(IsolationForestVoiceModel(self.model.model_path).status()["ready"])

    def test_manifest_integrity(self):
        self.model.train_demo()
        self.model.model_path.write_bytes(b"changed-model-bytes")
        self.assertFalse(self.model.status()["ready"])
        with self.assertRaisesRegex(ValueError, "não treinado"):
            self.model.analyze(self.root / "no.wav")

    def test_reference_training_with_twelve_separate_wavs(self):
        folder = self.root / "references"
        for seed in range(12):
            extension = ".WAV" if seed % 2 else ".wav"
            write_pcm16(folder / f"sample_{seed:02}{extension}", make_synthetic_signal(600 + seed))
        state = self.model.train_from_directory(folder)
        self.assertEqual(state["mode"], "reference_wav")
        self.assertEqual(state["reference_count"], 12)
        self.assertNotIn(str(folder), self.model.manifest_path.read_text())
        self.assertNotIn("sample_", self.model.manifest_path.read_text())

    def test_minimum_training_examples_and_bad_format(self):
        folder = self.root / "references"
        folder.mkdir()
        write_pcm16(folder / "one.wav", make_synthetic_signal(1))
        with self.assertRaisesRegex(ValueError, "12"):
            self.model.train_from_directory(folder)
        invalid = self.root / "sample.wav"
        write_pcm16(invalid, make_synthetic_signal(1), sample_rate=8000)
        with self.assertRaisesRegex(ValueError, "16 kHz"):
            features_from_wav(invalid)

    def test_math_guards(self):
        with self.assertRaises(ValueError):
            label_outlier(float("nan"))
        with self.assertRaises(ValueError):
            feature_vector({})
        self.assertEqual(label_outlier(-0.01), "outlier")
        self.assertEqual(label_outlier(0.01), "inlier")

    def test_application_saves_audio_event_and_review_alert_without_azure(self):
        self.model.train_demo()
        demo = self.model.prepare_demo(self.root / "demo")
        store = SqlitePatientStore(self.root / "db.sqlite3")
        app = ApplicationService(store, object(), object(), GoogleAudioSet(),
                                 audio_inspector=LocalWavInspector(), voice_model=self.model)
        app.bootstrap()
        normal = app.analyze_voice("TC4-P001", demo["reference"], "demo-good.wav")
        altered = app.analyze_voice("TC4-P001", demo["altered"], "demo-altered.wav")
        self.assertEqual(normal["prediction"], "inlier")
        self.assertEqual(altered["prediction"], "outlier")
        history = app.media_events("TC4-P001", "audio")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["result"]["analysis"], "voice_model")
        alerts = app.alerts("TC4-P001")
        self.assertTrue(any(row["code"] == "VOICE_ACOUSTIC_OUTLIER" for row in alerts))
        evidence = json.loads(next(row["evidence_json"] for row in alerts
                                   if row["code"] == "VOICE_ACOUSTIC_OUTLIER"))
        self.assertFalse(evidence["clinical_assessment"])

    def test_azure_flow_keeps_optional_model_out_of_mandatory_transcription(self):
        class SpeechFake:
            def transcribe(self, path):
                return "Olá, esta é uma fala de teste fictícia."

            def analyze(self, text):
                return {"sentiment": "neutral", "key_phrases": [], "entities": []}

        self.model.train_demo()
        demo = self.model.prepare_demo(self.root / "demo")
        store = SqlitePatientStore(self.root / "db2.sqlite3")
        app = ApplicationService(store, SpeechFake(), object(), GoogleAudioSet(),
                                 audio_inspector=LocalWavInspector(), voice_model=self.model)
        app.bootstrap()
        # Os WAVs de bancada não contêm fala de verdade: fake apenas para testar contrato.
        result = app.process_audio("TC4-P001", demo["reference"], "ficticio.wav")
        self.assertEqual(result["azure"]["sentiment"], "neutral")
        self.assertNotIn("voice", result)
        self.assertEqual(len(app.media_events("TC4-P001", "audio")), 1)
        self.assertNotIn("voice", app.media_events("TC4-P001", "audio")[0]["result"])


if __name__ == "__main__":
    unittest.main()
