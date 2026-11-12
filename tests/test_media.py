"""Valida processamento local de mídia, sem Azure/MediaPipe/rede reais."""

from __future__ import annotations

import io
import math
import sys
import tempfile
import types
import unittest
import wave
import zipfile
from pathlib import Path
from unittest.mock import patch

from fase4.container import build_application
from fase4.application.service import ApplicationService
from fase4.domain.acoustics import analyze_pcm16
from fase4.infrastructure.adapters import GoogleAudioSet, LocalWavInspector, SqlitePatientStore
from fase4.infrastructure.pose_model import download_pose_model, pose_model_status
from fase4.infrastructure.wav import inspect_wav


def make_wav(path: Path, samples: list[int], channels: int = 1, rate: int = 16000):
    from array import array
    buffer = array("h", samples)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(buffer.tobytes())


class AcousticTests(unittest.TestCase):
    def test_half_silence_half_tone_has_a_bounded_envelope(self):
        samples = [0] * 8000 + [int(6000 * math.sin(2 * math.pi * 220 * i / 16000))
                                for i in range(8000)]
        result = analyze_pcm16(samples, sample_rate=16000)
        self.assertEqual(result["duration_seconds"], 1)
        self.assertAlmostEqual(result["low_energy_fraction"], 0.5)
        self.assertEqual(result["clipped_fraction"], 0)
        self.assertEqual(len(result["envelope"]), 4)
        self.assertEqual(result["interpretation"], "acoustic_signal_only_not_clinical")

    def test_invalid_signal_and_silent_file(self):
        with self.assertRaises(ValueError):
            analyze_pcm16([], 16000)
        with self.assertRaises(ValueError):
            analyze_pcm16([0], 0)
        with self.assertRaises(ValueError):
            analyze_pcm16([40000], 16000)
        silent = analyze_pcm16([0] * 1600, 16000)
        self.assertEqual(silent["rms_dbfs"], -120.0)

    def test_wav_inspection_and_service_persistence_without_cloud(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            wav_path = root / "consulta_encenada.wav"
            make_wav(wav_path, [0] * 16000)
            app = build_application(root / "app.sqlite3")
            app.bootstrap()
            result = app.inspect_audio("TC4-P001", wav_path, wav_path.name)
            self.assertTrue(result["azure_ready"])
            self.assertEqual(result["sample_rate"], 16000)
            self.assertEqual(result["low_energy_fraction"], 1)
            self.assertIn("envelope", result)
            self.assertIn("azure_hint", result)

            from fase4.infrastructure.database import connect
            with connect(root / "app.sqlite3") as con:
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM media_events WHERE modality='audio'"
                ).fetchone()[0], 1)

            stereo = root / "stereo.wav"
            make_wav(stereo, [2000, -2000] * 8000, channels=2, rate=44100)
            self.assertFalse(inspect_wav(stereo)["azure_ready"])
            not_wav = root / "bad.wav"
            not_wav.write_bytes(b"isto nao e WAV")
            with self.assertRaises(ValueError):
                inspect_wav(not_wav)

    def test_azure_use_case_uses_local_validation_before_fake_cloud(self):
        class FakeSpeech:
            calls = 0
            def transcribe(self, path):
                self.calls += 1
                return "Estou com falta de ar."
            def analyze(self, text):
                return {"sentiment": "neutral", "provider": "fake"}

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            good = root / "fictional.wav"
            bad = root / "stereo.wav"
            make_wav(good, [1000] * 16000)
            make_wav(bad, [1000, -1000] * 8000, channels=2)
            speech = FakeSpeech()
            app = ApplicationService(SqlitePatientStore(root / "db.sqlite3"), speech,
                                     pose=None, audioset=GoogleAudioSet(),
                                     audio_inspector=LocalWavInspector())
            app.bootstrap()
            result = app.process_audio("TC4-P001", good, "ficcional.wav")
            self.assertEqual(result["acoustic"]["duration_seconds"], 1)
            self.assertEqual(speech.calls, 1)
            with self.assertRaises(ValueError):
                app.process_audio("TC4-P001", bad, "stereo.wav")
            self.assertEqual(speech.calls, 1, "não chama Azure com formato inválido")


class PoseModelTests(unittest.TestCase):
    def test_official_model_download_is_bounded_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "models" / "pose_landmarker_lite.task"
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as fake_bundle:
                fake_bundle.writestr("pose_detector.tflite", b"D" * 2048)
                fake_bundle.writestr("pose_landmarks_detector.tflite", b"L" * 2048)
            with patch("fase4.infrastructure.pose_model.urlopen", return_value=io.BytesIO(buffer.getvalue())) as fetch:
                first = download_pose_model(target)
                second = download_pose_model(target)
                self.assertEqual(fetch.call_count, 1)
                self.assertTrue(first["ready"])
                self.assertTrue(second["ready"])
                self.assertIn("sha256", first)
            self.assertGreater(pose_model_status(target)["size_bytes"], 4000)

    def test_invalid_existing_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "model.task"
            target.write_bytes(b"broken")
            with self.assertRaises(ValueError):
                download_pose_model(target)


class PosePipelineTests(unittest.TestCase):
    def test_video_sampling_timestamps_and_joint_angles_with_fake_sdks(self):
        from fase4.infrastructure.pose import analyze_pose_video, inspect_video

        class FakeCapture:
            def __init__(self, _):
                self.cursor = 0
            def isOpened(self):
                return True
            def get(self, key):
                return {1: 6, 2: 30.0, 3: 640, 4: 480}[key]
            def read(self):
                self.cursor += 1
                return self.cursor <= 6, object()
            def release(self):
                pass

        cv2 = types.SimpleNamespace(
            VideoCapture=FakeCapture, CAP_PROP_FRAME_COUNT=1, CAP_PROP_FPS=2,
            CAP_PROP_FRAME_WIDTH=3, CAP_PROP_FRAME_HEIGHT=4,
            COLOR_BGR2RGB=5, cvtColor=lambda image, color: image,
        )

        points = [types.SimpleNamespace(x=0.0, y=0.0, visibility=1.0) for _ in range(33)]
        for a, b, c in ((23, 25, 27), (24, 26, 28), (11, 13, 15), (12, 14, 16)):
            points[a] = types.SimpleNamespace(x=0.0, y=1.0, visibility=1.0)
            points[b] = types.SimpleNamespace(x=0.0, y=0.0, visibility=1.0)
            points[c] = types.SimpleNamespace(x=1.0, y=0.0, visibility=1.0)

        class FakeLandmarker:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return None
            def detect_for_video(self, image, ms):
                return types.SimpleNamespace(pose_landmarks=[points])

        mediapipe = types.SimpleNamespace(
            Image=lambda **kw: object(), ImageFormat=types.SimpleNamespace(SRGB=1),
            tasks=types.SimpleNamespace(
                BaseOptions=lambda **kw: object(),
                vision=types.SimpleNamespace(
                    PoseLandmarkerOptions=lambda **kw: object(),
                    RunningMode=types.SimpleNamespace(VIDEO=1),
                    PoseLandmarker=types.SimpleNamespace(
                        create_from_options=lambda opts: FakeLandmarker()),
                ),
            ),
        )

        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "demo.mp4"
            video.write_bytes(b"dummy file")
            model = Path(folder) / "pose.task"
            model.write_bytes(b"fake model; SDK is a double")
            with patch.dict(sys.modules, {"cv2": cv2, "mediapipe": mediapipe}):
                metadata = inspect_video(video)
                self.assertEqual(metadata["duration_seconds"], 0.2)
                rows = analyze_pose_video(video, model, sample_every=5)
            self.assertEqual(len(rows), 2)
            self.assertAlmostEqual(rows[0]["left_knee"], 90)
            self.assertAlmostEqual(rows[0]["left_elbow"], 90)
            self.assertTrue(rows[0]["pose_detected"])
            self.assertEqual(rows[0]["time_seconds"], 0)
            self.assertTrue(rows[0]["observed_at"].startswith("2026-01-01"))
            self.assertEqual(rows[0]["source"], rows[1]["source"])


if __name__ == "__main__":
    unittest.main()
