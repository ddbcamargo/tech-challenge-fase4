"""Contratos matemáticos do detector acústico — nenhum diagnóstico clínico."""

from __future__ import annotations

import math

FEATURE_NAMES = (
    "rms_dbfs", "low_energy_fraction", "clipped_fraction",
    "rms_variability_db", "zero_crossing_rate", "spectral_centroid_hz",
    "spectral_flatness", "pitch_median_hz", "pitch_variability_hz",
    "voiced_fraction",
)
MODEL_VERSION = "voice-acoustics-v1"


def feature_vector(features: dict) -> list[float]:
    """Validar mesma ordem na etapa de treino e inferência."""
    try:
        vector = [float(features[name]) for name in FEATURE_NAMES]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Características acústicas ausentes ou inválidas") from exc
    if not all(math.isfinite(value) for value in vector):
        raise ValueError("Características acústicas não finitas")
    if any(features[key] < 0 or features[key] > 1 for key in
           ("low_energy_fraction", "clipped_fraction", "zero_crossing_rate",
            "spectral_flatness", "voiced_fraction")):
        raise ValueError("Frações acústicas fora do intervalo 0..1")
    return vector


def label_outlier(decision: float) -> str:
    """Apenas comparação estatística com a referência: <0 é fora do padrão."""
    if not math.isfinite(decision):
        raise ValueError("Score acústico inválido")
    return "outlier" if decision < 0 else "inlier"
