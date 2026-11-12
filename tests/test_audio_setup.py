"""Teste do fluxo único: não confundir um baseline demonstrativo com AudioSet real."""
from pathlib import Path
from unittest.mock import patch

import pytest

from fase4.interfaces.audio_setup import ensure_voice_ready, setup_audio


class StubAudioApplication:
    def __init__(self, train_wavs: int = 0):
        self.train_wavs = train_wavs
        self.state = {"ready": False, "mode": None}
        self.stratified_samples = object()
        self.selected = False
        self.csv_calls = 0
        self.demo_calls = 0
        self.official_calls = 0

    def voice_model_status(self):
        return dict(self.state)

    def train_voice_demo(self):
        self.demo_calls += 1
        self.state = {"ready": True, "mode": "synthetic_demo", "reference_count": 48}
        return dict(self.state)

    def prepare_voice_demo(self):
        return {"reference": "data/demo/ref.wav", "altered": "data/demo/altered.wav"}

    def prepare_datasets(self, path):
        self.csv_calls += 1
        return {"ready": True}

    def audioset_stratified_status(self):
        if not self.selected:
            return {"ready": False, "items": [], "by_category": []}
        return {"ready": True, "selected": 96, "available": self.train_wavs,
                "by_category": [{"split": "balanced_train", "category": "Speech",
                                 "available": self.train_wavs}]}

    def audioset_stratified_select(self, seed, train, evaluation):
        self.selected = True
        return self.audioset_stratified_status()

    def audioset_train_category(self, category):
        self.official_calls += 1
        if category != "Speech" or self.train_wavs < 12:
            raise ValueError("dados insuficientes")
        self.state = {"ready": True, "mode": "audioset_speech_reference",
                      "reference_count": self.train_wavs}
        return dict(self.state)


def test_fallback_trains_demo_only_and_does_not_request_media():
    app = StubAudioApplication()
    result = setup_audio(app, official_download=False)
    assert result["model"]["ready"]
    assert result["model"]["mode"] == "synthetic_demo"
    assert not result["real_audioset_trained"]
    assert result["fetched"] == []
    assert app.csv_calls == 0
    assert app.demo_calls == 1
    assert app.official_calls == 0
    assert any("NÃO treinado" in warning for warning in result["warnings"])


def test_official_wavs_take_priority_over_demo_and_remain_on_next_run():
    app = StubAudioApplication(train_wavs=14)
    result = setup_audio(app)
    assert app.csv_calls == 1
    assert result["real_audioset_trained"] is True
    assert result["model"]["mode"] == "audioset_speech_reference"
    assert app.demo_calls == 0
    assert app.official_calls == 1
    following = ensure_voice_ready(app)
    assert following["model"]["mode"] == "audioset_speech_reference"
    assert app.official_calls == 1


def test_demonstration_is_promoted_if_real_wavs_arrive_later():
    app = StubAudioApplication()
    one = ensure_voice_ready(app)
    assert one["model"]["mode"] == "synthetic_demo"
    app.selected = True
    app.train_wavs = 12
    two = ensure_voice_ready(app)
    assert two["model"]["mode"] == "audioset_speech_reference"
    assert app.official_calls == 1


def test_online_fetch_is_strictly_opt_in_and_requires_rights():
    app = StubAudioApplication()
    with pytest.raises(ValueError, match="confirmação"):
        setup_audio(app, online_permission=True, confirm_rights=False)
    with pytest.raises(ValueError, match="somente fonte"):
        setup_audio(app, online_permission=True, source_dir=Path("videos"), confirm_rights=True)
    with patch("fase4.interfaces.audio_setup.AuthorizedAudioSetFetcher") as fetcher:
        fetcher.return_value.fetch.return_value = {"attempted": 10, "downloaded": 0, "failed": 10}
        result = setup_audio(app, official_download=False,
                             online_permission=True, confirm_rights=True, limit=10)
    assert result["fetched"][0]["attempted"] == 10
    assert result["real_audioset_trained"] is False


def test_setup_does_not_erase_real_training_if_catalog_unavailable():
    app = StubAudioApplication()
    app.state = {"ready": True, "mode": "audioset_speech_reference", "reference_count": 20}
    result = setup_audio(app, official_download=False)
    assert result["model"]["mode"] == "audioset_speech_reference"
    assert app.demo_calls == 0


def test_real_application_startup_has_model_and_example(tmp_path, monkeypatch):
    """Confirma que o usuário não precisa clicar em Treinar para testar WAV."""
    from fase4.container import build_application
    monkeypatch.chdir(tmp_path)
    app = build_application(tmp_path / "local.sqlite3")
    first = ensure_voice_ready(app)
    assert first["model"]["ready"]
    assert first["model"]["mode"] == "synthetic_demo"
    assert Path(first["examples"]["altered"]).is_file()
    app.bootstrap()
    report = app.analyze_voice("TC4-P001", first["examples"]["altered"], "exemplo.wav")
    assert report["reference_mode"] == "synthetic_demo"
    assert report["prediction"] == "outlier"
    assert report["clinical_assessment"] is False
    second = ensure_voice_ready(app)
    assert second["model"]["trained_at"] == first["model"]["trained_at"]


def test_cli_run_only_starts_required_ui_without_training(monkeypatch):
    from fase4.interfaces import cli
    from unittest.mock import Mock
    fake_application = Mock()
    fake_application.bootstrap.return_value = 25
    mock_setup = Mock(return_value={
        "model": {"mode": "synthetic_demo", "reference_count": 48}, "warnings": []
    })
    mock_launch = Mock(return_value=0)
    monkeypatch.setattr(cli, "build_application", lambda db: fake_application)
    monkeypatch.setattr(cli, "_launch", mock_launch)
    monkeypatch.setattr("fase4.interfaces.audio_setup.setup_audio", mock_setup)
    assert cli.main(["run"]) == 0
    mock_setup.assert_not_called()
    assert mock_launch.call_count == 1


def test_setup_reuses_existing_official_model_when_selection_unchanged(tmp_path):
    from fase4.infrastructure.datasets.catalog import file_sha256
    app = StubAudioApplication(train_wavs=15)
    app.selected = True
    selection = tmp_path / "selection.json"
    selection.write_text('{"selected":15}', encoding="utf-8")
    app.stratified_samples = type("Samples", (), {"selection_path": selection})()
    app.state = {"ready": True, "mode": "audioset_speech_reference",
                 "reference_count": 15,
                 "provenance": {"label": "Speech", "selection_sha256": file_sha256(selection)}}
    result = setup_audio(app, official_download=False)
    assert result["real_audioset_trained"]
    assert result["training"][0]["reused"] is True
    assert app.official_calls == 0
