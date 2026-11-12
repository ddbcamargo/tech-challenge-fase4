"""Modelo público oficial MediaPipe (download explícito, nunca no startup)."""

from __future__ import annotations

import hashlib
import os
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlopen

# URL obtida da tabela de modelos na documentação oficial do Google AI Edge.
POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)
MAX_MODEL_BYTES = 20 * 1024 * 1024


def pose_model_status(path: str | Path) -> dict:
    target = Path(path)
    valid = target.is_file() and 1024 < target.stat().st_size <= MAX_MODEL_BYTES
    if valid:
        try:
            with zipfile.ZipFile(target) as bundle:
                names = {item.filename: item.file_size for item in bundle.infolist()}
                valid = all(names.get(name, 0) > 1024 for name in (
                    "pose_detector.tflite", "pose_landmarks_detector.tflite"))
        except (zipfile.BadZipFile, OSError):
            valid = False
    return {"ready": valid, "path": str(target),
            "size_bytes": target.stat().st_size if target.is_file() else 0,
            "provider": "Google MediaPipe Pose Landmarker Lite"}


def download_pose_model(path: str | Path) -> dict:
    """Cria modelo local sem sobrescrever arquivos preexistentes."""
    target = Path(path)
    if target.exists():
        status = pose_model_status(target)
        if not status["ready"]:
            raise ValueError("Arquivo de modelo existente é inválido; revise o caminho")
        return status

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".pose-model-",
                                         delete=False) as handle:
            temporary_path = Path(handle.name)
            size = 0
            with urlopen(POSE_MODEL_URL, timeout=45) as response:
                while block := response.read(64 * 1024):
                    size += len(block)
                    if size > MAX_MODEL_BYTES:
                        raise ValueError("Modelo acima de 20 MiB; download interrompido")
                    handle.write(block)
        if size <= 1024:
            raise ValueError("Download não retornou um modelo válido")
        if not pose_model_status(temporary_path)["ready"]:
            raise ValueError("Download não contém os modelos MediaPipe esperados")
        os.replace(temporary_path, target)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    status = pose_model_status(target)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for block in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(block)
    status["sha256"] = digest.hexdigest()
    status["source_url"] = POSE_MODEL_URL
    return status
