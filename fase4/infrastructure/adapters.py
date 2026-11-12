"""Implementações de portas: cada recurso externo fica atrás de um adaptador."""

from __future__ import annotations

import os
from contextlib import closing
from pathlib import Path

from ..domain.anomalies import Anomaly
from . import database
from .azure import analyze_transcript, transcribe_short_audio
from .datasets.audioset import read_label_map, read_segments
from .datasets.physionet import import_psv
from .pose import analyze_pose_video
from .pose_model import download_pose_model, pose_model_status
from .seed import seed_example_prescriptions, seed_patients, seed_movement_examples
from .wav import inspect_wav


class SqlitePatientStore:
    def __init__(self, path: str | Path):
        self.path = path

    def bootstrap(self) -> int:
        with closing(database.connect(self.path)) as con:
            database.initialize(con)
            created = seed_patients(con)
            seed_example_prescriptions(con)
            seed_movement_examples(con)
            return created

    def patients(self) -> list[dict]:
        with closing(database.connect(self.path)) as con:
            database.initialize(con)
            return database.list_patients(con)

    def vitals(self, patient_id: str) -> list[dict]:
        with closing(database.connect(self.path)) as con:
            database.initialize(con)
            return database.list_vitals(con, patient_id)

    def movements(self, patient_id: str) -> list[dict]:
        with closing(database.connect(self.path)) as con:
            database.initialize(con)
            return database.list_movement(con, patient_id)

    def prescriptions(self, patient_id: str) -> list[dict]:
        with closing(database.connect(self.path)) as con:
            database.initialize(con)
            return [dict(row) for row in con.execute(
                "SELECT medication, dose, unit, frequency, valid_from FROM prescriptions "
                "WHERE patient_id=? ORDER BY valid_from", (patient_id,)
            )]

    def alerts(self, patient_id: str | None = None) -> list[dict]:
        with closing(database.connect(self.path)) as con:
            database.initialize(con)
            return database.list_alerts(con, patient_id)

    def media_events(self, patient_id: str, modality: str = "audio",
                     limit: int = 20) -> list[dict]:
        with closing(database.connect(self.path)) as con:
            database.initialize(con)
            return database.list_media_events(con, patient_id, modality, limit)

    def review_alert(self, alert_id: int, patient_id: str, status: str) -> bool:
        with closing(database.connect(self.path)) as con:
            database.initialize(con)
            return database.review_alert(con, alert_id, patient_id, status)

    def save_alert(self, event: Anomaly) -> None:
        with closing(database.connect(self.path)) as con:
            database.initialize(con)
            database.add_alert(con, event.patient_id, event.observed_at, event.modality,
                               event.severity, event.code, event.description, event.evidence)

    def save_media_event(self, patient_id: str, modality: str,
                         source_name: str, result: dict) -> int:
        with closing(database.connect(self.path)) as con:
            database.initialize(con)
            return database.add_media_event(con, patient_id, modality, database.utc_now(),
                                            source_name, result)

    def import_physionet(self, path: str | Path, patient_id: str) -> int:
        with closing(database.connect(self.path)) as con:
            database.initialize(con)
            return import_psv(con, path, patient_id)


class AzureSpeechAndLanguage:
    def transcribe(self, path: str | Path) -> str:
        return transcribe_short_audio(path)

    def analyze(self, text: str) -> dict:
        return analyze_transcript(text)


class LocalWavInspector:
    def inspect(self, path: str | Path) -> dict:
        return inspect_wav(path)


class MediaPipePose:
    def __init__(self, model_path: str | Path | None):
        self.model_path = Path(model_path) if model_path else Path("models/pose_landmarker_lite.task")

    def status(self) -> dict:
        return pose_model_status(self.model_path)

    def prepare(self) -> dict:
        return download_pose_model(self.model_path)

    def inspect(self, path: str | Path) -> dict:
        from .pose import inspect_video
        return inspect_video(path)

    def analyze(self, path: str | Path) -> list[dict]:
        if not self.model_path.is_file():
            raise FileNotFoundError("Prepare o modelo MediaPipe pelo botão ou comando prepare-pose-model")
        return analyze_pose_video(path, self.model_path)


class GoogleAudioSet:
    def preview(self, path: str | Path, limit: int) -> list[dict]:
        classes_path = Path(path).with_name("class_labels_indices.csv")
        labels = read_label_map(classes_path) if classes_path.is_file() else {}
        return [
            {**segment.__dict__, "label_names": [labels.get(mid, mid) for mid in segment.label_ids]}
            for segment in read_segments(path, limit)
        ]

    def speech_examples(self, path: str | Path, limit: int) -> list[dict]:
        if limit <= 0:
            return []
        labels = read_label_map(Path(path).with_name("class_labels_indices.csv"))
        speech_ids = {mid for mid, name in labels.items() if name in {"Speech", "Conversation"}}
        return [
            {"youtube_id": row.youtube_id, "start_seconds": row.start_seconds,
             "end_seconds": row.end_seconds,
             "label_names": [labels.get(mid, mid) for mid in row.label_ids]}
            for row in read_segments(path) if set(row.label_ids) & speech_ids
        ][:limit]

