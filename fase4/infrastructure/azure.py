"""Azure Speech e Azure Language atrás de um adaptador.

Somente áudio fictício ou autorizado. Não gravar chaves, áudio ou erros brutos do SDK.
"""

from __future__ import annotations

import os
from pathlib import Path


class AzureNotConfigured(RuntimeError):
    """Uma integração foi invocada sem suas configurações obrigatórias."""


class AzureProcessingError(RuntimeError):
    """Erro seguro para exibição ao usuário; não contém resposta bruta do provedor."""

    def __init__(self, stage: str, guidance: str):
        self.stage = stage
        super().__init__(guidance)


def _require_config(*names: str) -> list[str]:
    values = [os.getenv(name, "").strip() for name in names]
    missing = [name for name, value in zip(names, values) if not value]
    if missing:
        raise AzureNotConfigured("Configuração ausente no .env: " + ", ".join(missing))
    return values


def transcribe_short_audio(path: str | Path, locale: str = "pt-BR") -> str:
    """Azure Speech de UMA fala curta; não é transcrição contínua de consultas."""
    key, region = _require_config("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION")
    if not Path(path).is_file():
        raise FileNotFoundError(f"WAV não encontrado: {Path(path).name}")
    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError as exc:
        raise AzureProcessingError("speech", "Instale a dependência azure-cognitiveservices-speech.") from exc

    try:
        config = speechsdk.SpeechConfig(subscription=key, region=region)
        config.speech_recognition_language = locale
        audio = speechsdk.audio.AudioConfig(filename=str(path))
        recognizer = speechsdk.SpeechRecognizer(speech_config=config, audio_config=audio)
        result = recognizer.recognize_once_async().get()
        if result.reason == speechsdk.ResultReason.NoMatch:
            raise AzureProcessingError(
                "speech", "Nenhuma fala foi reconhecida. Verifique o WAV e grave uma frase curta em pt-BR."
            )
        if result.reason == speechsdk.ResultReason.Canceled:
            raise AzureProcessingError(
                "speech", "O Azure Speech cancelou o reconhecimento. Confira chave, região, "
                "cota F0 e conectividade no portal."
            )
        if result.reason != speechsdk.ResultReason.RecognizedSpeech or not result.text.strip():
            raise AzureProcessingError("speech", "O Azure Speech não retornou uma transcrição válida.")
        return result.text.strip()
    except AzureProcessingError:
        raise
    except Exception as exc:
        # Não propagar detalhes do provedor: podem conter URL, tokens ou cabeçalhos.
        raise AzureProcessingError(
            "speech", "Falha na chamada Speech. Verifique conectividade, região e acesso ao serviço."
        ) from exc


def analyze_transcript(text: str, language: str = "pt") -> dict:
    """Sentimento, frases-chave e entidades; não gera diagnóstico clínico."""
    if not text.strip():
        raise ValueError("Não há texto para análise. Faça a transcrição primeiro.")
    key, endpoint = _require_config("AZURE_LANGUAGE_KEY", "AZURE_LANGUAGE_ENDPOINT")
    if not endpoint.startswith("https://"):
        raise AzureNotConfigured("AZURE_LANGUAGE_ENDPOINT deve começar com https://")
    try:
        from azure.ai.textanalytics import TextAnalyticsClient
        from azure.core.credentials import AzureKeyCredential
    except ImportError as exc:
        raise AzureProcessingError("language", "Instale a dependência azure-ai-textanalytics.") from exc

    try:
        with TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key)) as client:
            sentiment = client.analyze_sentiment([text], language=language)[0]
            phrases = client.extract_key_phrases([text], language=language)[0]
            entities = client.recognize_entities([text], language=language)[0]
        for output in (sentiment, phrases, entities):
            if getattr(output, "is_error", False):
                raise AzureProcessingError(
                    "language", "O Azure Language recusou uma das análises. "
                    "Confira idioma, tamanho do texto, chave e cota do serviço."
                )
        scores = getattr(sentiment, "confidence_scores", None)
        confidence = ({name: round(float(getattr(scores, name)), 4)
                       for name in ("positive", "neutral", "negative")
                       if getattr(scores, name, None) is not None} if scores else {})
        return {
            "sentiment": sentiment.sentiment,
            "sentiment_scores": confidence,
            "key_phrases": list(phrases.key_phrases),
            "entities": [
                {"text": entity.text, "category": entity.category}
                for entity in entities.entities
            ],
            "provider": "azure-language",
            "clinical_assessment": False,
        }
    except AzureProcessingError:
        raise
    except Exception as exc:
        raise AzureProcessingError(
            "language", "Falha na chamada Language. Confira chave, endpoint HTTPS, "
            "cota F0 e conectividade."
        ) from exc
