"""Adaptador MediaPipe Tasks para estimativa de postura em video."""

from __future__ import annotations

import math
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_VIDEO_BYTES = 60 * 1024 * 1024
MAX_VIDEO_SECONDS = 120


def angle_degrees(a: tuple[float, float], b: tuple[float, float],
                  c: tuple[float, float]) -> float | None:
    ax, ay = a[0] - b[0], a[1] - b[1]
    cx, cy = c[0] - b[0], c[1] - b[1]
    length = math.hypot(ax, ay) * math.hypot(cx, cy)
    if length < 1e-10:
        return None
    cos_value = max(-1.0, min(1.0, (ax * cx + ay * cy) / length))
    return math.degrees(math.acos(cos_value))


def inspect_video(video_path: str | Path) -> dict:
    """Lê metadados do MP4 sem estimar postura; exige somente OpenCV."""
    import cv2

    path = Path(video_path)
    if path.stat().st_size > MAX_VIDEO_BYTES:
        raise ValueError("Vídeo excede 60 MiB; utilize um trecho curto")
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError("Vídeo não pode ser aberto pelo OpenCV")
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if fps <= 0 or not math.isfinite(fps) or width <= 0 or height <= 0:
            raise ValueError("Vídeo com metadados inválidos")
        seconds = frames / fps if frames > 0 else 0.0
        if seconds > MAX_VIDEO_SECONDS:
            raise ValueError("Vídeo maior que dois minutos; recorte o trecho")
        return {"frames": frames, "fps": round(fps, 3), "width": width,
                "height": height, "duration_seconds": round(seconds, 3)}
    finally:
        cap.release()


def analyze_pose_video(video_path: str | Path, model_path: str | Path,
                       sample_every: int = 5) -> list[dict]:
    """Retorna serie temporal de angulos de joelho; modelo .task nao acompanha repo."""
    if sample_every < 1:
        raise ValueError("sample_every deve ser >= 1")
    if not Path(model_path).is_file():
        raise FileNotFoundError("Baixe o modelo oficial Pose Landmarker .task")
    import cv2
    import mediapipe as mp

    metadata = inspect_video(video_path)
    digest = hashlib.sha256(Path(video_path).read_bytes()).hexdigest()[:16]
    source = f"video-replay:{digest}"
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("Video nao pode ser aberto")
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_poses=1,
    )
    frames = []
    # Relógio artificial, estável entre importações do mesmo vídeo.
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    fps = metadata["fps"]
    try:
        with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
            index = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if index % sample_every == 0:
                    ms = int(index * 1000 / fps)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    output = detector.detect_for_video(image, ms)
                    sample = {"observed_at": (start + timedelta(milliseconds=ms)).isoformat(),
                              "time_seconds": round(ms / 1000, 3),
                              "source": source, "pose_detected": False,
                              "left_knee": None, "right_knee": None,
                              "left_elbow": None, "right_elbow": None}
                    if output.pose_landmarks:
                        points = output.pose_landmarks[0]
                        sample["pose_detected"] = True
                        joints = {"left_knee": (23, 25, 27),
                                  "right_knee": (24, 26, 28),
                                  "left_elbow": (11, 13, 15),
                                  "right_elbow": (12, 14, 16)}
                        for name, indices in joints.items():
                            if all((getattr(points[n], "visibility", 1.0) or 0) >= 0.5
                                   for n in indices):
                                a, b, c = ((points[n].x, points[n].y) for n in indices)
                                sample[name] = angle_degrees(a, b, c)
                    frames.append(sample)
                index += 1
    finally:
        cap.release()
    return frames

