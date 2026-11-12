"""Extração acústica de WAV PCM16, com NumPy e sem serviços externos.

Features caracterizam o arquivo/gravação; NÃO reconhecem doenças ou emoções.
"""

from __future__ import annotations

import sys
import wave
from array import array
from pathlib import Path

import numpy as np

from ..domain.acoustics import analyze_pcm16
from ..domain.voice import feature_vector
from .wav import MAX_WAV_BYTES


def read_voice_wav(path: str | Path) -> tuple[np.ndarray, int]:
    file = Path(path)
    if not file.is_file() or file.stat().st_size > MAX_WAV_BYTES:
        raise ValueError("WAV inexistente ou acima de 16 MiB")
    try:
        with wave.open(str(file), "rb") as audio:
            if (audio.getsampwidth() != 2 or audio.getcomptype() != "NONE" or
                    audio.getnchannels() != 1 or audio.getframerate() != 16000):
                raise ValueError("Detector vocal requer WAV PCM16 mono, 16 kHz")
            if not 0.5 <= audio.getnframes() / 16000 <= 30:
                raise ValueError("Detector vocal requer WAV de 0,5 a 30 segundos")
            content = audio.readframes(audio.getnframes())
    except (wave.Error, EOFError) as exc:
        raise ValueError("WAV PCM16 inválido") from exc
    decoded = array("h")
    decoded.frombytes(content)
    if sys.byteorder != "little":
        decoded.byteswap()
    return np.asarray(decoded, dtype=np.int16), 16000


def extract_voice_features(samples: np.ndarray, sample_rate: int = 16000) -> dict:
    """Resumos reprodutíveis de energia, espectro, periodicidade e silêncio.

    Autocorrelação no pitch é estimativa aproximada e pode falhar em ruído.
    """
    if sample_rate != 16000:
        raise ValueError("Somente 16 kHz para comparação com a referência")
    signal = np.asarray(samples)
    if signal.ndim != 1 or not 8000 <= signal.size <= 30 * sample_rate:
        raise ValueError("Amostras insuficientes ou duração excessiva")
    if not np.all(np.isfinite(signal)) or np.max(np.abs(signal.astype(np.float64))) > 32768:
        raise ValueError("Sinal PCM16 inválido")
    signal = signal.astype(np.float64)
    basic = analyze_pcm16(signal.astype(np.int16).tolist(), sample_rate)
    normalized = signal / 32768.0
    frame_size = int(sample_rate * 0.04)
    # Até 80 janelas, para a inferência ser rápida mesmo em 30 segundos.
    offsets = np.linspace(0, max(0, signal.size - frame_size), num=min(80, max(1, signal.size // frame_size)), dtype=int)
    frames = np.stack([normalized[offset:offset + frame_size] for offset in offsets])
    window = np.hanning(frame_size)
    power = np.mean(frames ** 2, axis=1)
    rms_db = 10 * np.log10(np.maximum(power, 1e-12))
    active = power > 1e-5  # ~ -50 dBFS, limiar acústico não clínico
    vari = float(np.std(rms_db[active])) if np.count_nonzero(active) >= 2 else 0.0
    zcr = np.mean((frames[:, 1:] * frames[:, :-1]) < 0, axis=1)
    active_zcr = float(np.mean(zcr[active])) if np.any(active) else 0.0
    spectrum = np.abs(np.fft.rfft(frames * window, axis=1)) + 1e-10
    freq = np.fft.rfftfreq(frame_size, 1.0 / sample_rate)
    centroids = np.sum(spectrum * freq, axis=1) / np.sum(spectrum, axis=1)
    flatness = np.exp(np.mean(np.log(spectrum), axis=1)) / np.mean(spectrum, axis=1)
    centroid = float(np.mean(centroids[active])) if np.any(active) else 0.0
    flat = float(np.mean(flatness[active])) if np.any(active) else 1.0
    pitches = []
    min_lag = sample_rate // 420
    max_lag = sample_rate // 75
    for frame in frames[active]:
        frame = frame - np.mean(frame)
        fft = np.fft.rfft(frame, n=2048)
        autocorr = np.fft.irfft(np.abs(fft) ** 2, n=2048)[:frame.size]
        lag = min_lag + int(np.argmax(autocorr[min_lag:max_lag + 1]))
        if autocorr[0] > 1e-9 and autocorr[lag] / autocorr[0] > 0.55:
            pitches.append(sample_rate / lag)
    pitch_median = float(np.median(pitches)) if pitches else 0.0
    pitch_var = float(np.std(pitches)) if len(pitches) >= 2 else 0.0
    voiced = len(pitches) / max(1, len(frames))
    result = {
        "rms_dbfs": basic["rms_dbfs"],
        "low_energy_fraction": basic["low_energy_fraction"],
        "clipped_fraction": basic["clipped_fraction"],
        "rms_variability_db": round(vari, 5),
        "zero_crossing_rate": round(active_zcr, 7),
        "spectral_centroid_hz": round(centroid, 4),
        "spectral_flatness": round(float(np.clip(flat, 0.0, 1.0)), 7),
        "pitch_median_hz": round(pitch_median, 4),
        "pitch_variability_hz": round(pitch_var, 4),
        "voiced_fraction": round(voiced, 6),
    }
    feature_vector(result)
    return result


def features_from_wav(path: str | Path) -> dict:
    samples, rate = read_voice_wav(path)
    return extract_voice_features(samples, rate)
