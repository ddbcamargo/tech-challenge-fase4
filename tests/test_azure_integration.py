"""Testes de contrato da etapa 0.7 sem chamadas de nuvem nem credenciais reais."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from fase4.application.service import ApplicationService
from fase4.infrastructure.adapters import (AzureSpeechAndLanguage, GoogleAudioSet,
                                          LocalWavInspector, SqlitePatientStore)
from fase4.infrastructure.azure import (
    AzureNotConfigured, AzureProcessingError, analyze_transcript, transcribe_short_audio,
)


def stub_modules():
    """Substitui apenas símbolos do SDK necessários à integração Python."""
    reasons = SimpleNamespace(RecognizedSpeech="ok", NoMatch="no_match", Canceled="canceled")
    speech = ModuleType("azure.cognitiveservices.speech")
    speech.ResultReason = reasons
    speech.result = SimpleNamespace(reason="ok", text="Relato fictício de falta de ar")
    speech.SpeechConfig = lambda subscription, region: SimpleNamespace(
        subscription=subscription, region=region, speech_recognition_language=None
    )
    speech.audio = SimpleNamespace(AudioConfig=lambda filename: SimpleNamespace(filename=filename))
    speech.SpeechRecognizer = lambda speech_config, audio_config: SimpleNamespace(
        recognize_once_async=lambda: SimpleNamespace(get=lambda: speech.result)
    )
    lang = ModuleType("azure.ai.textanalytics")

    class FakeClient:
        def __init__(self, endpoint, credential):
            self.endpoint = endpoint
            self.credential = credential
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return None
        def analyze_sentiment(self, docs, language):
            return [SimpleNamespace(is_error=False, sentiment="neutral")]
        def extract_key_phrases(self, docs, language):
            return [SimpleNamespace(is_error=False, key_phrases=["falta de ar"])]
        def recognize_entities(self, docs, language):
            return [SimpleNamespace(is_error=False, entities=[SimpleNamespace(
                text="teste", category="Other")])]

    lang.TextAnalyticsClient = FakeClient
    creds = ModuleType("azure.core.credentials")
    creds.AzureKeyCredential = lambda key: SimpleNamespace(key=key)
    azure = ModuleType("azure")
    cogn = ModuleType("azure.cognitiveservices")
    ai = ModuleType("azure.ai")
    core = ModuleType("azure.core")
    azure.cognitiveservices = cogn
    azure.ai = ai
    azure.core = core
    cogn.speech = speech
    ai.textanalytics = lang
    core.credentials = creds
    return {
        "azure": azure, "azure.cognitiveservices": cogn,
        "azure.cognitiveservices.speech": speech, "azure.ai": ai,
        "azure.ai.textanalytics": lang, "azure.core": core,
        "azure.core.credentials": creds,
    }, speech, lang


class AzureAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.wav = Path(self.temp.name) / "synthetic.wav"
        self.wav.write_bytes(b"fake-file-for-sdk-stub")
        self.env = {
            "AZURE_SPEECH_KEY": "FAKE_TEST_KEY_DO_NOT_SHARE",
            "AZURE_SPEECH_REGION": "brazilsouth",
            "AZURE_LANGUAGE_KEY": "FAKE_LANGUAGE_KEY_DO_NOT_SHARE",
            "AZURE_LANGUAGE_ENDPOINT": "https://fake.example.test/",
        }
        self.modules, self.speech, self.lang = stub_modules()

    def tearDown(self):
        self.temp.cleanup()

    def test_speech_transcribes_using_sdk_without_cloud(self):
        with patch.dict(sys.modules, self.modules), patch.dict(os.environ, self.env, clear=True):
            self.assertIn("falta de ar", transcribe_short_audio(self.wav))

    def test_speech_no_match_has_actionable_safe_message(self):
        self.speech.result = SimpleNamespace(reason="no_match", text="")
        with patch.dict(sys.modules, self.modules), patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(AzureProcessingError, "Nenhuma fala"):
                transcribe_short_audio(self.wav)

    def test_speech_cancelled_never_exposes_key_or_error_details(self):
        self.speech.result = SimpleNamespace(reason="canceled", text="", error_details="secret")
        with patch.dict(sys.modules, self.modules), patch.dict(os.environ, self.env, clear=True):
            with self.assertRaises(AzureProcessingError) as caught:
                transcribe_short_audio(self.wav)
            self.assertNotIn("FAKE_TEST_KEY", str(caught.exception))
            self.assertNotIn("secret", str(caught.exception))
            self.assertIn("cota F0", str(caught.exception))

    def test_missing_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(AzureNotConfigured):
                transcribe_short_audio(self.wav)
            with self.assertRaises(AzureNotConfigured):
                analyze_transcript("teste")

    def test_language_returns_all_three_expected_analyses(self):
        with patch.dict(sys.modules, self.modules), patch.dict(os.environ, self.env, clear=True):
            result = analyze_transcript("Este relato é inteiramente fictício")
            self.assertEqual(result["sentiment"], "neutral")
            self.assertEqual(result["key_phrases"], ["falta de ar"])
            self.assertEqual(result["entities"][0]["category"], "Other")
            self.assertFalse(result["clinical_assessment"])

    def test_language_error_is_sanitized(self):
        def fail(_):
            raise RuntimeError("secret-header-FAKE_LANGUAGE_KEY")
        with patch.dict(sys.modules, self.modules), patch.dict(os.environ, self.env, clear=True):
            with patch.object(self.lang.TextAnalyticsClient, "analyze_sentiment", fail):
                with self.assertRaises(AzureProcessingError) as caught:
                    analyze_transcript("texto fictício")
                self.assertNotIn("secret-header", str(caught.exception))

    def test_end_to_end_application_using_both_azure_sdk_stubs(self):
        import wave
        self.speech.result = SimpleNamespace(reason="ok", text="Estou com falta de ar")
        with wave.open(str(self.wav), "wb") as file:
            file.setnchannels(1)
            file.setsampwidth(2)
            file.setframerate(16000)
            file.writeframes(b"\x00\x00" * 16000)
        store = SqlitePatientStore(Path(self.temp.name) / "azure_simulated.sqlite3")
        store.bootstrap()
        app = ApplicationService(store, AzureSpeechAndLanguage(), None,
                                 GoogleAudioSet(), audio_inspector=LocalWavInspector())
        with patch.dict(sys.modules, self.modules), patch.dict(os.environ, self.env, clear=True):
            report = app.process_audio("TC4-P001", self.wav, "consulta-ficticia.wav")
        self.assertEqual(report["azure"]["provider"], "azure-language")
        self.assertEqual(len(app.media_events("TC4-P001")), 1)
        self.assertEqual(app.alerts("TC4-P001")[0]["code"], "AUDIO_TERMS")

    def test_invalid_language_endpoint_is_rejected(self):
        env = {**self.env, "AZURE_LANGUAGE_ENDPOINT": "http://unsafe.example.test"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(AzureNotConfigured, "https"):
                analyze_transcript("teste")


class AudioHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SqlitePatientStore(Path(self.temp.name) / "fresh.sqlite3")
        self.store.bootstrap()

    def tearDown(self):
        self.temp.cleanup()

    def test_analysis_is_persisted_and_retrieved_by_patient(self):
        class FakeSpeech:
            def transcribe(self, path):
                return "Estou com falta de ar"
            def analyze(self, text):
                return {"sentiment": "negative", "key_phrases": ["falta de ar"],
                        "entities": [], "provider": "fake", "clinical_assessment": False}

        app = ApplicationService(self.store, FakeSpeech(), None, GoogleAudioSet())
        result = app.process_audio("TC4-P001", "fake.wav", "consulta-encenada.wav")
        history = app.media_events("TC4-P001")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["result"]["transcript"], result["transcript"])
        self.assertEqual(app.media_events("TC4-P002"), [])
        self.assertEqual(app.media_events("TC4-P001", "video"), [])
        self.assertEqual(app.alerts("TC4-P001")[0]["code"], "AUDIO_TERMS")

    def test_failed_language_call_does_not_save_partial_analysis(self):
        class FailingSpeech:
            def transcribe(self, path):
                return "Exemplo fictício"
            def analyze(self, text):
                raise AzureProcessingError("language", "Falha simulada")

        app = ApplicationService(self.store, FailingSpeech(), None, GoogleAudioSet())
        with self.assertRaises(AzureProcessingError):
            app.process_audio("TC4-P001", "fake.wav", "consulta.wav")
        self.assertEqual(app.media_events("TC4-P001"), [])

    def test_media_events_validate_modality_and_limit(self):
        with self.assertRaises(ValueError):
            self.store.media_events("TC4-P001", "text")
        with self.assertRaises(ValueError):
            self.store.media_events("TC4-P001", "audio", 500)


if __name__ == "__main__":
    unittest.main()
