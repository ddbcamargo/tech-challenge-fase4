"""Cobertura dos requisitos obrigatórios e migração do projeto 0.8.x."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fase4.application.service import ApplicationService
from fase4.domain.anomalies import detect_movement_anomalies
from fase4.domain.voice_signals import describe_voice_indicators
from fase4.infrastructure.adapters import GoogleAudioSet, SqlitePatientStore
from fase4.infrastructure import database


class FakeSpeech:
    def transcribe(self, path):
        return "Estou com falta de ar e dor no peito."

    def analyze(self, text):
        return {"provider": "azure-stub", "sentiment": "negative",
                "key_phrases": ["falta de ar"], "entities": []}


class FakePose:
    def analyze(self, path):
        return [{"observed_at": f"2026-01-01T00:00:{n:02}+00:00",
                 "source": "video-synthetic", "pose_detected": True,
                 "time_seconds": n,
                 "left_knee": value, "right_knee": 90,
                 "left_elbow": 90, "right_elbow": 90}
                for n, value in enumerate([90, 90, 89, 91, 90, 142])]


def make_app(tmp_path):
    app = ApplicationService(SqlitePatientStore(tmp_path / "tc4.sqlite3"),
                             FakeSpeech(), FakePose(), GoogleAudioSet())
    app.bootstrap()
    return app


def test_seeded_movement_does_not_require_real_patient_data(tmp_path):
    app = make_app(tmp_path)
    records = app.movements("TC4-P001")
    assert len(records) == 9
    assert all(row["source"] == "synthetic_ward" for row in records)
    events = app.scan_movements("TC4-P001")
    assert {event.code for event in events} == {"MOVEMENT_INACTIVITY", "MOVEMENT_DISPLACEMENT"}
    assert not app.movements("TC4-P002")


def test_voice_indicators_are_descriptive_only():
    report = describe_voice_indicators({"low_energy_fraction": 0.8,
                                         "clipped_fraction": 0.03,
                                         "duration_seconds": 15},
                                        "Teste com fala simulada")
    assert {row["code"] for row in report} == {"LONG_LOW_ENERGY", "CLIPPED_AUDIO"}
    assert all("disartria" not in row["description"].lower() for row in report)


def test_multimodal_fusion_persists_and_is_idempotent(tmp_path):
    app = make_app(tmp_path)
    result = app.scan_monitoring("TC4-P001")
    assert result["counts"]["prescriptions"] >= 1
    assert result["counts"]["movement"] >= 1
    alert_types = {row["modality"] for row in app.alerts("TC4-P001")}
    assert "prescription" in alert_types
    assert "movement" in alert_types
    assert "multimodal" in alert_types
    fusion_count = sum(row["modality"] == "multimodal" for row in app.alerts("TC4-P001"))
    assert app.correlate_alerts("TC4-P001") is None
    assert sum(row["modality"] == "multimodal" for row in app.alerts("TC4-P001")) == fusion_count
    multi = next(row for row in app.alerts("TC4-P001") if row["modality"] == "multimodal")
    evidence = json.loads(multi["evidence_json"])
    assert evidence["source_alert_ids"]
    assert evidence["time_basis"] == "local_registration_time"
    assert evidence["clinical_assessment"] is False


def test_audio_video_reporting_produces_evidence_and_correlates(tmp_path):
    app = make_app(tmp_path)
    audio = app.process_audio("TC4-P001", "fake.wav", "consulta-encenada.wav")
    assert audio["critical_terms"]
    assert audio["azure"]["provider"] == "azure-stub"
    video = app.process_video("TC4-P001", "fake.mp4", "fisio-encenado.mp4")
    assert video["alert_count"] == 1
    assert video["joint_summary"]["left_knee"]["samples"] == 6
    assert video["anomalies"][0]["joint"].startswith("POSE_LEFT_KNEE")
    saved_video = app.media_events("TC4-P001", "video")[0]["result"]
    assert saved_video["joint_summary"] == video["joint_summary"]
    assert any(row["modality"] == "multimodal" for row in app.alerts("TC4-P001"))


def test_existing_v085_alerts_table_is_upgraded_without_losing_records(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with database.connect(path) as con:
        database.initialize(con)
        con.execute("ALTER TABLE alerts RENAME TO alerts_old")
        con.execute("CREATE TABLE alerts AS SELECT id, patient_id, observed_at, modality, severity, "
                    "code, description, evidence_json, status FROM alerts_old WHERE 0")
        con.execute("DROP TABLE alerts_old")
        con.execute("INSERT INTO alerts (id,patient_id,observed_at,modality,severity,code,description,evidence_json,status) "
                    "VALUES (1,'TC4-P001','2026-01-01T00:00:00+00:00','vitals','warning','OLD','legacy','{}','pending_review')")
        con.commit()
        database.initialize(con)
        row = con.execute("SELECT code, recorded_at FROM alerts WHERE id=1").fetchone()
    assert row["code"] == "OLD"
    assert row["recorded_at"] == "2026-01-01T00:00:00+00:00"


def test_fusion_patient_isolation_and_no_cross_patient_merge(tmp_path):
    app = make_app(tmp_path)
    app.scan_prescriptions("TC4-P001")
    assert app.correlate_alerts("TC4-P001") is None
    assert app.correlate_alerts("TC4-P002") is None


def test_new_modality_updates_fusion_with_new_evidence_even_same_second(tmp_path):
    app = make_app(tmp_path)
    app.scan_monitoring("TC4-P001")
    prior = [row for row in app.alerts("TC4-P001") if row["modality"] == "multimodal"]
    assert len(prior) == 1
    app.process_audio("TC4-P001", "fake.wav", "consulta.wav")
    new_fusions = [row for row in app.alerts("TC4-P001") if row["modality"] == "multimodal"]
    assert len(new_fusions) == 2
    evidence = json.loads(new_fusions[0]["evidence_json"])
    assert "audio" in evidence["modalities"]
    assert len(evidence["source_alert_ids"]) > len(
        json.loads(prior[0]["evidence_json"])["source_alert_ids"])
