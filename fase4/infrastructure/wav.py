"""Leitor WAV controlado, com limite de tamanho e sem dependências externas."""

from __future__ import annotations

import sys
import wave
from array import array
from pathlib import Path

from ..domain.acoustics import analyze_pcm16

MAX_WAV_BYTES = 16 * 1024 * 1024
MAX_WAV_SECONDS = 90


def inspect_wav(path: str | Path) -> dict:
    """Inspeciona áudio PCM 16-bit mono/estéreo; não transcreve fala."""
    target = Path(path)
    if target.stat().st_size > MAX_WAV_BYTES:
        raise ValueError("Arquivo WAV excede 16 MiB; use um trecho curto")

    try:
        with wave.open(str(target), "rb") as wav:
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            frames = wav.getnframes()
            if wav.getcomptype() != "NONE" or wav.getsampwidth() != 2:
                raise ValueError("Use WAV PCM 16-bit não comprimido")
            if channels not in (1, 2):
                raise ValueError("O WAV deve ter um ou dois canais")
            if not sample_rate or frames / sample_rate > MAX_WAV_SECONDS:
                raise ValueError("Use áudio de no máximo 90 segundos")
            raw = wav.readframes(frames)
    except (wave.Error, EOFError) as exc:
        raise ValueError("O arquivo não é um WAV PCM válido") from exc

    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    if channels == 2:
        mono = [(samples[index] + samples[index + 1]) // 2
                for index in range(0, len(samples), 2)]
    else:
        mono = samples
    summary = analyze_pcm16(mono, sample_rate)
    summary["channels"] = channels
    summary["azure_ready"] = channels == 1 and sample_rate in (8000, 16000)
    summary["azure_hint"] = ("Formato recomendado para Azure: WAV PCM 16-bit, "
                             "mono, 16 kHz (ou 8 kHz).")
    return summary
