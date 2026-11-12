"""Regressão de apresentação e alertas com evidências da fala encenada."""

import json
from pathlib import Path

from fase4.application.service import ApplicationService
from fase4.domain.text_flags import critical_evidence, critical_terms
from fase4.infrastructure.adapters import GoogleAudioSet, SqlitePatientStore
from fase4.interfaces.audio_presentation import audio_view


TRANSCRIPT = ("Bom dia, doutor. Estou muito preocupada. Essas dores nas mãos e "
              "nos punhos têm me impedido de fazer tarefas simples no meu dia a dia.")


class FakeAzure:
    def transcribe(self, path):
        return TRANSCRIPT

    def analyze(self, text):
        return {
            "sentiment": "mixed", "sentiment_scores": {"positive": .09, "negative": .63, "neutral": .28},
            "key_phrases": ["mãos", "Bom dia", "dores", "mãos", "punhos"],
            "entities": [{"text": "doutor", "category": "PersonType"},
                         {"text": "dia a dia", "category": "DateTime"}],
        }


def test_exact_phrases_from_fictitious_transcript():
    evidence = critical_evidence(TRANSCRIPT)
    assert [item["code"] for item in evidence] == ["PAIN", "FUNCTIONAL_LIMITATION"]
    assert [item["text"] for item in evidence] == [
        "dores nas mãos e nos punhos", "têm me impedido de fazer tarefas simples",
    ]
    for item in evidence:
        assert TRANSCRIPT[item["start"]:item["end"]] == item["text"]


def test_common_existing_critical_terms_and_negation():
    assert "falta de ar" in critical_terms("Estou com falta de ar e dor no peito.")
    assert "dor no peito" in critical_terms("Estou com falta de ar e dor no peito.")
    assert critical_terms("Não tenho dor e estou sem cansaço.") == []
    assert critical_terms("A sessão ocorreu normalmente.") == []


def test_audio_view_hides_internal_fields_and_translates_azure_response():
    report = {"transcript": TRANSCRIPT, "azure": FakeAzure().analyze(TRANSCRIPT),
              "critical_evidence": critical_evidence(TRANSCRIPT),
              "acoustic": {"duration_seconds": 8.94, "rms_dbfs": -25.17,
                           "low_energy_fraction": .168, "clipped_fraction": 0},
              "voice": {"reference_mode": "synthetic_demo", "model_version": "test"}}
    view = audio_view(report)
    assert view["sentiment"] == "Misto"
    assert view["sentiment_scores"]["Negativo"] == 63.0
    assert view["key_phrases"] == ["mãos", "Bom dia", "dores", "punhos"]
    assert view["entities"][0]["Categoria"] == "Tipo de pessoa"
    assert "synthetic_demo" not in json.dumps(view)
    assert len(view["critical_evidence"]) == 2
    assert view["duration_seconds"] == 8.94


def test_audio_view_is_backward_compatible_and_handles_empty_azure_results():
    report = {"transcript": "histórico", "azure": {"sentiment": "neutral"},
              "critical_terms": ["dor no peito"]}
    view = audio_view(report)
    assert view["sentiment"] == "Neutro"
    assert view["key_phrases"] == []
    assert view["entities"] == []
    assert view["critical_evidence"][0]["Trecho original"] == "dor no peito"


def test_audio_alert_is_linked_to_patient_and_record_and_fused(tmp_path):
    app = ApplicationService(SqlitePatientStore(tmp_path / "fase4.sqlite3"),
                             FakeAzure(), None, GoogleAudioSet())
    app.bootstrap()
    app.scan_prescriptions("TC4-P001")
    result = app.process_audio("TC4-P001", "fake.wav", "consulta_ficticia.wav")
    assert result["critical_terms"] == [
        "dores nas mãos e nos punhos", "têm me impedido de fazer tarefas simples",
    ]
    records = app.media_events("TC4-P001", "audio")
    assert len(records) == 1
    alerts = app.alerts("TC4-P001")
    audio_alert = next(row for row in alerts if row["modality"] == "audio")
    evidence = json.loads(audio_alert["evidence_json"])
    assert evidence["media_event_id"] == records[0]["id"]
    assert evidence["sentiment"] == "mixed"
    assert evidence["matched_evidence"][0]["text"] == "dores nas mãos e nos punhos"
    assert any(row["modality"] == "multimodal" for row in alerts)
    assert app.media_events("TC4-P002", "audio") == []
    assert all(row["patient_id"] == "TC4-P001" for row in alerts)


def test_active_streamlit_does_not_show_optional_training_panel():
    content = (Path(__file__).resolve().parents[1] / "fase4/interfaces/clinical_dashboard.py").read_text()
    sidebar = (Path(__file__).resolve().parents[1] / "fase4/interfaces/dashboard.py").read_text()
    assert "Estado do modelo experimental" not in content
    assert "Experimentação opcional" not in content
    assert "synthetic_demo" not in content
    assert "Treinamento próprio:" not in sidebar
    legacy = (Path(__file__).resolve().parents[1] / "fase4/interfaces/dashboard_sections.py").read_text()
    assert "synthetic_demo" not in legacy
    assert "def audio_tab(" not in legacy
