"""Modelo Isolation Forest treinado localmente e armazenado no diretório models/.

Baseline sintético NÃO pode ser usado para estimar risco clínico real.
"""

from __future__ import annotations

import hashlib
import json
import os
import wave
from array import array
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ..domain.voice import FEATURE_NAMES, MODEL_VERSION, feature_vector, label_outlier
from .voice_features import extract_voice_features, features_from_wav

MIN_REFERENCE_FILES = 12
MAX_REFERENCE_FILES = 100


def make_synthetic_signal(seed: int, abnormal: bool = False) -> np.ndarray:
    """Sinal sintético de bancada (NÃO representa fala nem condição médica)."""
    rng = np.random.default_rng(seed)
    rate, duration = 16000, 2.0
    t = np.arange(int(rate * duration)) / rate
    fundamental = rng.uniform(145, 230)
    # Harmônicos e modulação simulam um sinal periódico, não uma voz humana.
    carrier = (np.sin(2 * np.pi * fundamental * t) +
               0.31 * np.sin(2 * np.pi * fundamental * 2 * t) +
               0.1 * np.sin(2 * np.pi * fundamental * 3 * t)) / 1.41
    syllabic = np.clip(0.65 + 0.3 * np.sin(2 * np.pi * rng.uniform(2, 4) * t), 0, 1)
    noise = rng.normal(0, rng.uniform(0.002, 0.008), size=t.size)
    audio = (rng.uniform(0.12, 0.27) * syllabic * carrier + noise)
    if abnormal:
        audio[int(0.3 * rate):int(1.15 * rate)] = 0
        audio[int(1.4 * rate):int(1.85 * rate)] *= 12
    return (np.clip(audio, -1, 1) * 32767).astype(np.int16)


def write_pcm16(path: str | Path, samples: np.ndarray, sample_rate: int = 16000) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = array("h", np.asarray(samples, dtype=np.int16).tolist())
    with wave.open(str(target), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(data.tobytes())


class IsolationForestVoiceModel:
    def __init__(self, model_path: str | Path = "models/voice_anomaly.joblib"):
        self.model_path = Path(model_path)
        self.manifest_path = self.model_path.with_suffix(".json")

    def status(self) -> dict:
        if not self.model_path.is_file() or not self.manifest_path.is_file():
            return {"ready": False, "path": str(self.model_path), "mode": None}
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if (manifest.get("version") != MODEL_VERSION or
                    manifest.get("feature_names") != list(FEATURE_NAMES) or
                    manifest.get("sha256") != hashlib.sha256(self.model_path.read_bytes()).hexdigest()):
                raise ValueError("Manifesto do modelo incompatível ou alterado")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return {"ready": False, "path": str(self.model_path), "mode": None,
                    "error": str(exc)}
        return {"ready": True, "path": str(self.model_path), "mode": manifest["mode"],
                "reference_count": manifest["reference_count"], "trained_at": manifest["trained_at"],
                "version": MODEL_VERSION,
                "provenance": manifest.get("provenance")}

    def _train(self, features: list[dict], mode: str,
               provenance: dict | None = None) -> dict:
        if len(features) < MIN_REFERENCE_FILES:
            raise ValueError(f"Necessárias no mínimo {MIN_REFERENCE_FILES} referências independentes")
        vectors = np.asarray([feature_vector(item) for item in features])
        if not np.all(np.isfinite(vectors)):
            raise ValueError("Características inválidas")
        pipe = Pipeline([
            ("scale", StandardScaler()),
            ("forest", IsolationForest(n_estimators=120, contamination=0.10, random_state=42)),
        ])
        pipe.fit(vectors)
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.model_path.with_suffix(".pending")
        try:
            joblib.dump(pipe, tmp)
            os.replace(tmp, self.model_path)
        finally:
            tmp.unlink(missing_ok=True)
        manifest = {
            "version": MODEL_VERSION, "mode": mode,
            "feature_names": list(FEATURE_NAMES),
            "reference_count": len(features),
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(self.model_path.read_bytes()).hexdigest(),
            "disclaimer": "Academic acoustic deviation only; not clinical validation",
        }
        if provenance:
            manifest["provenance"] = provenance
        self.manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.status()

    def train_demo(self) -> dict:
        features = [extract_voice_features(make_synthetic_signal(seed))
                    for seed in range(120, 120 + 48)]
        return self._train(features, "synthetic_demo")

    def train_from_directory(self, directory: str | Path) -> dict:
        folder = Path(directory)
        if not folder.is_dir():
            raise ValueError("Diretório de referências não encontrado")
        # No Windows, glob("*.wav") também encontra WAV maiúsculo: concatenar
        # os dois globs duplica cada arquivo e distorce reference_count/treino.
        paths = sorted(
            (path for path in folder.iterdir()
             if path.is_file() and path.suffix.lower() == ".wav"),
            key=lambda path: path.name.lower(),
        )
        if not MIN_REFERENCE_FILES <= len(paths) <= MAX_REFERENCE_FILES:
            raise ValueError(f"Forneça de {MIN_REFERENCE_FILES} a {MAX_REFERENCE_FILES} WAVs de referência")
        features = [features_from_wav(path) for path in paths]
        return self._train(features, "reference_wav")

    def train_from_audioset(self, paths: list[Path], provenance: dict) -> dict:
        """Treina com trechos reais selecionados do split oficial balanced_train.

        O manifest da fonte registra a seleção, os WAVs e a limitação de
        verificação de autoria, sem alegar validação clínica.
        """
        category = provenance.get("label")
        if (provenance.get("dataset") != "Google AudioSet v1" or
                provenance.get("split") != "balanced_train" or
                category not in {"Speech", "Breathing", "Cough", "Wheeze"} or
                (category != "Speech" and provenance.get("curation") != "stratified")):
            raise ValueError("Proveniência AudioSet incompatível com o treino acústico")
        if not MIN_REFERENCE_FILES <= len(paths) <= MAX_REFERENCE_FILES:
            raise ValueError("É necessário importar 12 a 100 WAVs AudioSet da mesma categoria")
        if len({path.name for path in paths}) != len(paths):
            raise ValueError("Trechos duplicados não podem entrar no treinamento")
        features = [features_from_wav(path) for path in paths]
        mode = ("audioset_speech_reference" if category == "Speech" else
                f"audioset_{category.lower()}_acoustic_reference")
        return self._train(features, mode, provenance)

    def analyze(self, path: str | Path) -> dict:
        state = self.status()
        if not state["ready"]:
            raise ValueError("Modelo vocal não treinado. Treine no painel ou pelo comando voice-train-demo")
        features = features_from_wav(path)
        # Apenas carregue joblib gerado localmente por esta aplicação; não aceite arquivos de terceiros.
        model = joblib.load(self.model_path)
        decision = float(model.decision_function(np.asarray([feature_vector(features)]))[0])
        ml_prediction = label_outlier(decision)
        # Sinais artificialmente saturados ou com grande trecho sem energia são
        # problemas de qualidade observáveis, não rótulos médicos.
        quality_flags = []
        if features["clipped_fraction"] >= 0.01:
            quality_flags.append("CLIPPING")
        if features["low_energy_fraction"] >= 0.35:
            quality_flags.append("LOW_ENERGY")
        return {
            "prediction": "outlier" if ml_prediction == "outlier" or quality_flags else "inlier",
            "ml_prediction": ml_prediction,
            "quality_flags": quality_flags,
            "decision_basis": ("ml_and_signal_quality" if quality_flags else "ml_only"),
            "anomaly_score": round(decision, 6),
            "features": features,
            "reference_mode": state["mode"],
            "reference_count": state["reference_count"],
            "model_version": MODEL_VERSION,
            "clinical_assessment": False,
            "interpretation": "desvio_acustico_estatistico_sem_diagnostico",
        }

    def prepare_demo(self, directory: str | Path = "data/demo/voice") -> dict:
        folder = Path(directory)
        normal = folder / "sinal_sintetico_referencia.wav"
        anomalous = folder / "sinal_sintetico_alterado.wav"
        write_pcm16(normal, make_synthetic_signal(168))
        write_pcm16(anomalous, make_synthetic_signal(168, abnormal=True))
        return {"reference": str(normal), "altered": str(anomalous),
                "warning": "Sinais sintéticos não contêm fala; NÃO envie ao Azure Speech"}
