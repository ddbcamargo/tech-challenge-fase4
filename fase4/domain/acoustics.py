"""Descritores acústicos objetivos, sem interpretação clínica da voz.

Este módulo opera em PCM mono já decodificado, sem ler arquivos ou usar Azure.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def analyze_pcm16(samples: Sequence[int], sample_rate: int,
                  window_ms: int = 250) -> dict:
    """Retorna energia, silêncio aproximado e saturação de um sinal PCM16.

    Silêncio (< -40 dBFS por janela) indica apenas baixa energia acústica.
    Não inferir disartria, fadiga, emoção, doença ou qualidade de consulta.
    """
    if sample_rate < 1000 or sample_rate > 192_000:
        raise ValueError("Taxa de amostragem fora do intervalo suportado")
    if window_ms < 50 or window_ms > 1000:
        raise ValueError("Janela acústica deve estar entre 50 e 1000 ms")
    if not samples:
        raise ValueError("Áudio sem amostras")
    if any(not -32768 <= sample <= 32767 for sample in samples):
        raise ValueError("Amostra fora do formato PCM16")

    count = len(samples)
    energy = sum(sample * sample for sample in samples)
    peak = max(abs(sample) for sample in samples)
    clipping = sum(abs(sample) >= 32700 for sample in samples)

    def dbfs(power: float) -> float:
        if power <= 0:
            return -120.0
        return round(10 * math.log10(power / (32768.0 * 32768.0)), 2)

    hop = max(1, round(sample_rate * window_ms / 1000))
    windows = []
    silent_samples = 0
    for start in range(0, count, hop):
        chunk = samples[start:start + hop]
        power = sum(value * value for value in chunk) / len(chunk)
        current_dbfs = dbfs(power)
        if current_dbfs < -40:
            silent_samples += len(chunk)
        windows.append({"second": round(start / sample_rate, 3),
                        "rms_dbfs": current_dbfs})

    return {
        "duration_seconds": round(count / sample_rate, 3),
        "sample_rate": sample_rate,
        "rms_dbfs": dbfs(energy / count),
        "peak_dbfs": dbfs(peak * peak),
        "low_energy_fraction": round(silent_samples / count, 3),
        "clipped_fraction": round(clipping / count, 5),
        "envelope": windows,
        "interpretation": "acoustic_signal_only_not_clinical",
    }
