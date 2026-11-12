"""Casos de uso únicos para CLI, Streamlit e FastAPI."""

from __future__ import annotations

from pathlib import Path

from ..domain.anomalies import (Anomaly, detect_pose_outliers,
                                detect_prescription_changes, detect_vital_anomalies,
                                detect_movement_anomalies, fusion_alert)
from ..domain.text_flags import critical_terms, critical_evidence
from ..domain.voice_signals import describe_voice_indicators
from ..domain.replay import ReplayFrame, build_replay_frame, sources_for_replay
from .ports import (AudioInspector, AudioSetCatalog, AudioSetSamples,
                    StratifiedAudioSetCatalog, DatasetProvider, PatientStore,
                    PoseAnalyzer, SpeechAnalyzer, VoiceAnomalyModel)


class ApplicationService:
    def __init__(self, store: PatientStore, speech: SpeechAnalyzer,
                 pose: PoseAnalyzer, audioset: AudioSetCatalog,
                 datasets: DatasetProvider | None = None,
                 audio_inspector: AudioInspector | None = None,
                 voice_model: VoiceAnomalyModel | None = None,
                 audioset_samples: AudioSetSamples | None = None,
                 stratified_samples: StratifiedAudioSetCatalog | None = None):
        self.store = store
        self.speech = speech
        self.pose = pose
        self.audioset = audioset
        self.datasets = datasets
        self.audio_inspector = audio_inspector
        self.voice_model = voice_model
        self.audioset_samples = audioset_samples
        self.stratified_samples = stratified_samples

    def prepare_datasets(self, root: str | Path) -> dict:
        if self.datasets is None:
            raise RuntimeError("Provedor de datasets não configurado")
        return self.datasets.prepare(root)

    def validate_datasets(self, root: str | Path) -> dict:
        if self.datasets is None:
            raise RuntimeError("Provedor de datasets não configurado")
        return self.datasets.validate(root)

    def bootstrap(self) -> int:
        """Prepara schema e cria 25 pacientes fictícios, de forma idempotente."""
        return self.store.bootstrap()

    def patients(self) -> list[dict]:
        return self.store.patients()

    def vitals(self, patient_id: str) -> list[dict]:
        return self.store.vitals(patient_id)

    def movements(self, patient_id: str) -> list[dict]:
        return self.store.movements(patient_id)

    def replay_sources(self, patient_id: str) -> list[dict]:
        """Lista séries isoladas disponíveis para reprodução."""
        return sources_for_replay(self.vitals(patient_id))

    def replay_preview(self, patient_id: str, source: str, position: int = 0) -> ReplayFrame:
        """Consulta o estado atual sem persistir alertas."""
        return build_replay_frame(patient_id, self.vitals(patient_id), source, position)

    def replay_next(self, patient_id: str, source: str, position: int) -> ReplayFrame:
        """Avança uma hora disponível e grava apenas os novos desvios daquele passo."""
        records = self.vitals(patient_id)
        current = build_replay_frame(patient_id, records, source, position)
        if position == current.total_steps:
            raise ValueError("O replay já chegou à última observação")
        next_frame = build_replay_frame(patient_id, records, source, position + 1)
        self._persist(next_frame.new_events)
        if next_frame.new_events:
            self.correlate_alerts(patient_id)
        return next_frame

    def alerts(self, patient_id: str | None = None) -> list[dict]:
        return self.store.alerts(patient_id)

    def media_events(self, patient_id: str, modality: str = "audio",
                     limit: int = 20) -> list[dict]:
        """Consultas já processadas; dados do SQLite, sem chamar o Azure novamente."""
        return self.store.media_events(patient_id, modality, limit)

    def review_alert(self, alert_id: int, patient_id: str, status: str = "reviewed") -> bool:
        if status not in {"reviewed", "dismissed"}:
            raise ValueError("Use status reviewed ou dismissed")
        return self.store.review_alert(alert_id, patient_id, status)

    def import_physionet(self, path: str | Path, patient_id: str) -> int:
        return self.store.import_physionet(path, patient_id)

    def audioset_preview(self, path: str | Path, limit: int = 5) -> list[dict]:
        return self.audioset.preview(path, limit)

    def audioset_speech_examples(self, path: str | Path, limit: int = 5) -> list[dict]:
        """Consulta apenas os rótulos públicos ligados a fala, sem obter áudio."""
        return self.audioset.speech_examples(path, limit)

    def audioset_selection_status(self) -> dict:
        if self.audioset_samples is None:
            return {"ready": False, "selected": 0, "available": 0, "items": []}
        return self.audioset_samples.status()

    def audioset_select(self, label: str = "Speech", split: str = "balanced_train",
                        limit: int = 24) -> dict:
        if self.audioset_samples is None:
            raise RuntimeError("Curadoria AudioSet não configurada")
        return self.audioset_samples.select(label, split, limit)

    def audioset_import_clip(self, clip_id: str, path: str | Path) -> dict:
        if self.audioset_samples is None:
            raise RuntimeError("Curadoria AudioSet não configurada")
        return self.audioset_samples.import_clip(clip_id, path)

    def train_voice_audioset(self) -> dict:
        if self.audioset_samples is None or self.voice_model is None:
            raise RuntimeError("Curadoria ou detector vocal não configurados")
        paths, provenance = self.audioset_samples.training_references()
        return self.voice_model.train_from_audioset(paths, provenance)

    def audioset_stratified_select(self, seed: int = 42, train_quotas: dict | None = None,
                                  eval_quotas: dict | None = None) -> dict:
        if self.stratified_samples is None:
            raise RuntimeError("Curadoria estratificada não configurada")
        return self.stratified_samples.select(seed, train_quotas, eval_quotas)

    def audioset_stratified_status(self) -> dict:
        if self.stratified_samples is None:
            return {"ready": False, "items": [], "by_category": []}
        return self.stratified_samples.status()

    def audioset_stratified_import(self, clip_id: str, path: str | Path) -> dict:
        if self.stratified_samples is None:
            raise RuntimeError("Curadoria estratificada não configurada")
        return self.stratified_samples.import_clip(clip_id, path)

    def audioset_train_category(self, category: str) -> dict:
        if self.stratified_samples is None or self.voice_model is None:
            raise RuntimeError("Curadoria ou detector acústico não configurados")
        from ..infrastructure.datasets.audioset_stratified import TRAINABLE_CATEGORIES
        from ..infrastructure.voice_model import IsolationForestVoiceModel
        if category not in TRAINABLE_CATEGORIES:
            raise ValueError("Treino permitido: Speech, Breathing, Cough ou Wheeze")
        paths, provenance = self.stratified_samples.references(category, "balanced_train")
        if category == "Speech":
            model = self.voice_model
        else:
            model = IsolationForestVoiceModel(f"models/audioset_{category.lower()}.joblib")
        return model.train_from_audioset(paths, provenance)

    def audioset_evaluate_category(self, category: str) -> dict:
        """Relata taxa de desvio na avaliação, não acurácia ou diagnóstico."""
        from ..infrastructure.datasets.audioset_stratified import TRAINABLE_CATEGORIES
        from ..infrastructure.voice_model import IsolationForestVoiceModel
        if self.stratified_samples is None or category not in TRAINABLE_CATEGORIES:
            raise ValueError("Categoria não elegível para avaliação acústica")
        paths, _ = self.stratified_samples.references(category, "eval")
        if not paths:
            raise ValueError("Importe WAVs separados do split eval para analisar desvio")
        model = self.voice_model if category == "Speech" else IsolationForestVoiceModel(
            f"models/audioset_{category.lower()}.joblib")
        status = model.status()
        if not status["ready"] or (status.get("provenance") or {}).get("label") != category:
            raise ValueError("Treine o modelo da categoria com balanced_train antes de avaliar")
        from ..infrastructure.datasets.catalog import file_sha256
        if (status["provenance"].get("selection_sha256") !=
                file_sha256(self.stratified_samples.selection_path)):
            raise ValueError("Modelo treinado com outra seleção; refaça o treinamento")
        reports = [model.analyze(path) for path in paths]
        count = sum(report["ml_prediction"] == "outlier" for report in reports)
        return {"category": category, "split": "eval", "samples": len(paths),
                "model_outliers": count, "outlier_rate": round(count / len(paths), 4),
                "metric_note": "Taxa de desvio estatístico; NÃO representa acurácia de diagnóstico",
                "source_verified": False}

    def inspect_audio(self, patient_id: str, path: str | Path, source_name: str) -> dict:
        """Descritores acústicos locais sem Azure, sem diagnóstico e sem transcrição."""
        if self.audio_inspector is None:
            raise RuntimeError("Inspetor WAV não configurado")
        result = self.audio_inspector.inspect(path)
        self.store.save_media_event(patient_id, "audio", source_name,
                                    {"analysis": "local_wav", **result})
        return result

    def voice_model_status(self) -> dict:
        return self.voice_model.status() if self.voice_model else {"ready": False, "mode": None}

    def train_voice_demo(self) -> dict:
        if self.voice_model is None:
            raise RuntimeError("Detector vocal não configurado")
        return self.voice_model.train_demo()

    def train_voice_references(self, directory: str | Path) -> dict:
        if self.voice_model is None:
            raise RuntimeError("Detector vocal não configurado")
        return self.voice_model.train_from_directory(directory)

    def prepare_voice_demo(self) -> dict:
        if self.voice_model is None:
            raise RuntimeError("Detector vocal não configurado")
        return self.voice_model.prepare_demo()

    def _record_voice_alert(self, patient_id: str, report: dict, source_name: str) -> None:
        if report["prediction"] != "outlier":
            return
        from datetime import datetime, timezone
        from ..domain.anomalies import Anomaly
        self._persist([Anomaly(
            patient_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "audio", "info", "VOICE_ACOUSTIC_OUTLIER",
            "Desvio acústico estatístico (revisão acadêmica, sem diagnóstico)",
            {"source_name": Path(source_name).name, "model_version": report["model_version"],
             "reference_mode": report["reference_mode"],
             "anomaly_score": report["anomaly_score"], "clinical_assessment": False}
        )])

    def analyze_voice(self, patient_id: str, path: str | Path, source_name: str) -> dict:
        """Detector local sem nenhuma chamada Azure, com evidência armazenada no SQLite."""
        if self.voice_model is None:
            raise RuntimeError("Detector vocal não configurado")
        report = self.voice_model.analyze(path)
        self.store.save_media_event(patient_id, "audio", Path(source_name).name,
                                    {"analysis": "voice_model", "voice": report})
        self._record_voice_alert(patient_id, report, source_name)
        return report

    def pose_model_status(self) -> dict:
        return self.pose.status()

    def prepare_pose_model(self) -> dict:
        return self.pose.prepare()

    def inspect_video(self, path: str | Path) -> dict:
        return self.pose.inspect(path)

    def _persist(self, events: list[Anomaly]) -> list[Anomaly]:
        for event in events:
            self.store.save_alert(event)
        return events

    def scan_vitals(self, patient_id: str) -> list[Anomaly]:
        return self._persist(detect_vital_anomalies(patient_id, self.vitals(patient_id)))

    def scan_prescriptions(self, patient_id: str) -> list[Anomaly]:
        return self._persist(detect_prescription_changes(
            patient_id, self.store.prescriptions(patient_id)
        ))

    def scan_movements(self, patient_id: str) -> list[Anomaly]:
        return self._persist(detect_movement_anomalies(patient_id, self.movements(patient_id)))

    def scan_monitoring(self, patient_id: str) -> dict:
        """Executa verificações com evidência; dados de demonstração não são live."""
        results = {
            "vitals": len(self.scan_vitals(patient_id)),
            "prescriptions": len(self.scan_prescriptions(patient_id)),
            "movement": len(self.scan_movements(patient_id)),
        }
        merged = self.correlate_alerts(patient_id)
        return {"counts": results, "multimodal": merged is not None,
                "mode": "historical_replay_and_synthetic_demo"}

    def correlate_alerts(self, patient_id: str, window_minutes: int = 30) -> Anomaly | None:
        """Relaciona alertas de modalidades distintas pelo tempo de REGISTRO na demo.

        Tempo original do sinal é mantido em cada alerta; não equiparar o tempo
        de registro local a simultaneidade clínica real.
        """
        from datetime import datetime, timedelta, timezone
        if not 1 <= window_minutes <= 120:
            raise ValueError("Janela de fusão deve estar entre 1 e 120 minutos")
        now = datetime.now(timezone.utc)
        recent = []
        for row in self.store.alerts(patient_id):
            if row["modality"] == "multimodal" or row["status"] != "pending_review":
                continue
            recorded = row.get("recorded_at") or row["observed_at"]
            try:
                when = datetime.fromisoformat(recorded)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
            if timedelta(0) <= now - when <= timedelta(minutes=window_minutes):
                recent.append((row, when))
        if len({row["modality"] for row, _ in recent}) < 2:
            return None
        # Não emitir uma segunda fusão para exatamente os mesmos alertas-fonte.
        source_ids = sorted(row["id"] for row, _ in recent)
        import json
        for old in self.store.alerts(patient_id):
            if old["modality"] != "multimodal":
                continue
            try:
                evidence = json.loads(old["evidence_json"])
            except (ValueError, TypeError):
                continue
            if evidence.get("source_alert_ids") == source_ids:
                return None
        event_rows = [Anomaly(
            patient_id, at.isoformat(), row["modality"], row["severity"],
            row["code"], row["description"], {},
        ) for row, at in recent]
        fused = fusion_alert(patient_id, event_rows, window_minutes=window_minutes)
        if fused is None:
            return None
        evidence = {**fused.evidence,
                    "source_alert_ids": source_ids,
                    "original_observed_at": {str(row["id"]): row["observed_at"]
                                             for row, _ in recent},
                    "time_basis": "local_registration_time",
                    "clinical_assessment": False}
        fused = Anomaly(fused.patient_id, now.isoformat(timespec="microseconds"),
                        fused.modality, fused.severity, fused.code,
                        fused.description, evidence)
        self._persist([fused])
        return fused

    def process_audio(self, patient_id: str, path: str | Path,
                      source_name: str) -> dict:
        acoustic = self.audio_inspector.inspect(path) if self.audio_inspector else None
        if acoustic is not None and acoustic["duration_seconds"] > 30:
            raise ValueError("Azure recognize_once é limitado a fala curta; use até 30 segundos")
        if acoustic is not None and not acoustic["azure_ready"]:
            raise ValueError(acoustic["azure_hint"])
        transcript = self.speech.transcribe(path)
        if not transcript.strip():
            raise ValueError("O Speech não reconheceu fala; nenhum evento foi gravado")
        azure_result = self.speech.analyze(transcript)
        evidence = critical_evidence(transcript)
        terms = [item["text"] for item in evidence]
        indicators = describe_voice_indicators(acoustic, transcript)
        result = {"transcript": transcript, "azure": azure_result,
                  "acoustic": acoustic, "critical_terms": terms,
                  "critical_evidence": evidence,
                  "voice_indicators": indicators}
        media_event_id = self.store.save_media_event(patient_id, "audio", source_name, result)
        if terms:
            from datetime import datetime, timezone
            self._persist([Anomaly(
                patient_id, datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                "audio", "warning", "AUDIO_TERMS", "Trechos do relato para revisão",
                {"terms": terms, "matched_evidence": evidence,
                 "sentiment": azure_result.get("sentiment"),
                 "media_event_id": media_event_id,
                 "clinical_assessment": False,
                 "source_name": Path(source_name).name}
            )])
        if acoustic and not terms and indicators:
            from datetime import datetime, timezone
            self._persist([Anomaly(
                patient_id, datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                "audio", "info", "AUDIO_SIGNAL_REVIEW",
                "Qualidade ou pausas do sinal merecem revisão técnica",
                {"clipped_fraction": acoustic.get("clipped_fraction"),
                 "low_energy_fraction": acoustic.get("low_energy_fraction"),
                 "indicators": indicators,
                 "source_name": Path(source_name).name,
                 "clinical_assessment": False}
            )])
        self.correlate_alerts(patient_id)
        return result

    def process_video(self, patient_id: str, path: str | Path,
                      source_name: str) -> dict:
        samples = self.pose.analyze(path)
        events = self._persist([
            event for joint in ("left_knee", "right_knee", "left_elbow", "right_elbow")
            for event in detect_pose_outliers(patient_id, samples, angle_name=joint)
        ])
        detected = sum(bool(row.get("pose_detected", True)) for row in samples)
        from statistics import median
        joints = ("left_knee", "right_knee", "left_elbow", "right_elbow")
        metrics = {}
        for joint in joints:
            values = [float(row[joint]) for row in samples if row.get(joint) is not None]
            metrics[joint] = {
                "samples": len(values),
                "min_degrees": round(min(values), 2) if values else None,
                "max_degrees": round(max(values), 2) if values else None,
                "median_degrees": round(median(values), 2) if values else None,
            }
        result = {"samples": samples, "pose_detected_frames": detected,
                  "alert_count": len(events), "joint_summary": metrics,
                  "anomalies": [{"time": event.observed_at, "joint": event.code,
                                 "evidence": event.evidence} for event in events],
                  "method": "mediapipe_pose_landmarker_robust_mad",
                  "limitations": ["Referência derivada do próprio vídeo",
                                  "Não detecta falhas cirúrgicas nem diagnostica doenças"],
                  "clinical_assessment": False}
        self.store.save_media_event(patient_id, "video", source_name, result)
        self.correlate_alerts(patient_id)
        return result

