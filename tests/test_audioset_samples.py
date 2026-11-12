"""Testa curadoria AudioSet sem rede e sem publicar qualquer conteúdo de vídeo."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from fase4.application.service import ApplicationService
from fase4.infrastructure.datasets.audioset_samples import LocalAudioSetSamples
from fase4.infrastructure.datasets.catalog import OFFICIAL_FILES, prepare_datasets
from fase4.infrastructure.voice_model import IsolationForestVoiceModel, write_pcm16

SPEECH = "/m/09x0r"
COUGH = "/m/01b_21"
LABELS = f"index,mid,display_name\n0,{SPEECH},Speech\n1,{COUGH},Cough\n".encode()
PSV = b"HR|O2Sat|SBP|DBP|Resp|Temp\n80|98|120|80|16|36.5\n"


def segments(count: int, prefix: str = "vid") -> bytes:
    header = b"# example header\n# YTID, start_seconds, end_seconds, positive_labels\n"
    rows = [f'{prefix}{i:08d}, 0.000, 10.000, "{SPEECH}"\n'.encode()
            for i in range(count)]
    return header + b"".join(rows)


class AudioSetSamplesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.official = self.root / "official"
        payload = {
            "p100679.psv": PSV,
            "class_labels_indices.csv": LABELS,
            "balanced_train_segments.csv": segments(14),
            "eval_segments.csv": segments(2, "evl"),
        }
        with patch("fase4.infrastructure.datasets.catalog.urlopen",
                   side_effect=lambda url, timeout=30: io.BytesIO(next(
                       payload[spec.name] for spec in OFFICIAL_FILES if spec.url == url))):
            result = prepare_datasets(self.official)
        self.assertTrue(result["ready"])
        self.samples = LocalAudioSetSamples(self.official, self.root / "audioset")

    def wav(self, name: str = "ten_seconds.wav", seconds: int = 10, seed: int = 42):
        path = self.root / name
        rng = np.random.default_rng(seed)
        t = np.arange(16000 * seconds) / 16000
        signal = ((0.05 * np.sin(2 * np.pi * (150 + seed) * t)) +
                  rng.normal(0, 0.001, t.size))
        write_pcm16(path, np.asarray(signal * 32767, dtype=np.int16))
        return path

    def test_official_selection_only_does_not_claim_training_or_download_audio(self):
        state = self.samples.select("Speech", "balanced_train", 13)
        self.assertEqual((state["selected"], state["available"], state["missing"]), (13, 0, 13))
        self.assertFalse(state["source_verified"])
        self.assertEqual(state["items"][0]["youtube_id"], "vid00000000")
        self.assertIn("youtube.com", state["items"][0]["source_url"])
        self.assertFalse((self.root / "audioset/clips").exists())
        with self.assertRaisesRegex(ValueError, "Necessários"):
            self.samples.training_references()

    def test_import_duration_unknown_id_and_duplicate_rejected(self):
        state = self.samples.select(limit=12)
        clip_id = state["items"][0]["id"]
        with self.assertRaisesRegex(ValueError, "não pertence"):
            self.samples.import_clip("fake_000000_010000", self.wav())
        with self.assertRaisesRegex(ValueError, "Duração"):
            self.samples.import_clip(clip_id, self.wav("short.wav", seconds=2))
        result = self.samples.import_clip(clip_id, self.wav())
        self.assertFalse(result["source_verified"])
        self.assertEqual(self.samples.status()["available"], 1)
        with self.assertRaisesRegex(ValueError, "sobrescrito"):
            self.samples.import_clip(clip_id, self.wav())
        with self.assertRaisesRegex(ValueError, "Remova/mova"):
            self.samples.select(limit=13)

    def test_only_balanced_train_speech_can_train_reference(self):
        state = self.samples.select("Speech", "eval", 2)
        clip_id = state["items"][0]["id"]
        self.samples.import_clip(clip_id, self.wav())
        with self.assertRaisesRegex(ValueError, "balanced_train"):
            self.samples.training_references()

    def test_model_training_with_curated_wavs_records_provenance(self):
        selection = self.samples.select("Speech", "balanced_train", 12)
        for i, clip in enumerate(selection["items"]):
            self.samples.import_clip(clip["id"], self.wav(f"source{i}.wav", seed=i+10))
        paths, provenance = self.samples.training_references()
        self.assertEqual(len(paths), 12)
        self.assertEqual(provenance["dataset"], "Google AudioSet v1")
        self.assertEqual(provenance["split"], "balanced_train")
        self.assertEqual(len({x["name"] for x in provenance["files"]}), 12)
        model = IsolationForestVoiceModel(self.root / "models/voice.joblib")
        trained = model.train_from_audioset(paths, provenance)
        self.assertTrue(trained["ready"])
        self.assertEqual(trained["mode"], "audioset_speech_reference")
        self.assertEqual(trained["provenance"]["dataset"], "Google AudioSet v1")
        report = model.analyze(paths[0])
        self.assertEqual(report["reference_mode"], "audioset_speech_reference")
        self.assertFalse(report["clinical_assessment"])
        manifest = json.loads(model.manifest_path.read_text(encoding="utf-8"))
        self.assertFalse(manifest["provenance"]["source_verified"])

    def test_tampered_official_csv_makes_selection_invalid(self):
        self.samples.select(limit=12)
        (self.official / "balanced_train_segments.csv").write_text("alterado", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "alterado"):
            self.samples.status()


if __name__ == "__main__":
    unittest.main()
