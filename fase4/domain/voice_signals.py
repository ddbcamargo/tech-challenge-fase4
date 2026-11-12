"""Pistas acústicas exploratórias que NÃO diagnosticam sintomas ou patologias."""

from __future__ import annotations


def describe_voice_indicators(acoustic: dict | None, transcript: str) -> list[dict]:
    """Aponta padrões observáveis de áudio curto, não classifica doenças.

    Limiar é de qualidade/demonstração e não usa referência clínica. Pausas são
    frações de baixa energia estimadas, NÃO detecção confiável de respiração.
    """
    if acoustic is None:
        return []
    indicators = []
    low = float(acoustic.get("low_energy_fraction", 0))
    clipping = float(acoustic.get("clipped_fraction", 0))
    if low >= 0.7:
        indicators.append({"code": "LONG_LOW_ENERGY", "value": round(low, 3),
                           "description": "Alta fração de baixa energia; rever pausas/silêncio"})
    if clipping >= 0.01:
        indicators.append({"code": "CLIPPED_AUDIO", "value": round(clipping, 3),
                           "description": "Saturação do sinal pode comprometer a análise"})
    duration = float(acoustic.get("duration_seconds", 0) or 0)
    count = len(transcript.strip().split())
    # Só relatar velocidade aproximada quando houver fala suficiente.
    if duration >= 10 and count >= 10:
        words_per_minute = count / duration * 60
        if words_per_minute < 75:
            indicators.append({"code": "LOW_ESTIMATED_SPEECH_RATE",
                               "value": round(words_per_minute, 1),
                               "description": "Ritmo médio de palavras baixo para este trecho"})
    return indicators
