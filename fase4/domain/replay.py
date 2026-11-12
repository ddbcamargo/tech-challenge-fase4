"""Linha do tempo pura para reproduzir séries históricas sem telemetria real.

Um passo representa uma observação horária disponível em uma única origem.
Nenhuma medição futura é usada para detectar um desvio no passo atual.
"""

from __future__ import annotations

from dataclasses import dataclass

from .anomalies import Anomaly, detect_vital_anomalies


@dataclass(frozen=True)
class ReplayFrame:
    patient_id: str
    source: str
    position: int
    total_steps: int
    observed_at: str | None
    current_values: dict[str, float]
    history: list[dict]
    events: list[Anomaly]
    new_events: list[Anomaly]


def sources_for_replay(records: list[dict]) -> list[dict]:
    """Resume fontes disponíveis, sem juntar pacientes reais distintos."""
    grouped: dict[str, dict] = {}
    for row in records:
        source = str(row["source"])
        info = grouped.setdefault(source, {"source": source, "measurements": 0, "hours": set()})
        info["measurements"] += 1
        info["hours"].add(row["observed_at"])
    return [
        {"source": key, "measurements": value["measurements"], "hours": len(value["hours"])}
        for key, value in sorted(grouped.items())
    ]


def build_replay_frame(patient_id: str, records: list[dict], source: str,
                       position: int) -> ReplayFrame:
    """Monta estado até `position` (0 = antes do primeiro registro)."""
    selected = [row for row in records if row.get("source") == source]
    hours = sorted({row["observed_at"] for row in selected})
    if not hours:
        raise ValueError("Não há série de sinais vitais para essa origem")
    if not isinstance(position, int) or not 0 <= position <= len(hours):
        raise ValueError(f"Posição fora do replay: use entre 0 e {len(hours)}")

    allowed = set(hours[:position])
    history = sorted((row for row in selected if row["observed_at"] in allowed),
                     key=lambda row: (row["observed_at"], row["metric"]))
    current_time = hours[position - 1] if position else None
    values = {row["metric"]: float(row["value"]) for row in history
              if row["observed_at"] == current_time}
    events = detect_vital_anomalies(patient_id, history)
    new_events = [event for event in events if event.observed_at == current_time]

    return ReplayFrame(patient_id, source, position, len(hours), current_time,
                       values, history, events, new_events)
