"""Composition root: único lugar que escolhe as implementações concretas."""

from __future__ import annotations

import os
from pathlib import Path

from .application.service import ApplicationService
from .config import load_project_environment
from .infrastructure.adapters import (AzureSpeechAndLanguage, GoogleAudioSet,
                                      LocalWavInspector, MediaPipePose, SqlitePatientStore)
from .infrastructure.datasets.catalog import OfficialDatasets
from .infrastructure.datasets.audioset_samples import LocalAudioSetSamples
from .infrastructure.datasets.audioset_stratified import StratifiedAudioSetSamples
from .infrastructure.voice_model import IsolationForestVoiceModel


def build_application(db_path: str | Path | None = None) -> ApplicationService:
    load_project_environment()
    path = db_path or os.getenv("FASE4_DB_PATH", "data/fase4.sqlite3")
    return ApplicationService(
        SqlitePatientStore(path), AzureSpeechAndLanguage(),
        MediaPipePose(os.getenv("POSE_MODEL_PATH")), GoogleAudioSet(),
        OfficialDatasets(), LocalWavInspector(),
        IsolationForestVoiceModel(os.getenv("VOICE_MODEL_PATH", "models/voice_anomaly.joblib")),
        LocalAudioSetSamples(), StratifiedAudioSetSamples()
    )

