"""Regras de dominio: eventos estatisticos e administrativos, sem diagnostico."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median


@dataclass(frozen=True)
class Anomaly:
    patient_id: str
    observed_at: str
    modality: str
    severity: str
    code: str
    description: str
    evidence: dict


def robust_score(current: float, reference: list[float]) -> float:
    """Distancia robusta em MAD. Escala minima evita divisao por zero."""
    central = median(reference)
    mad = median([abs(value - central) for value in reference])
    return abs(current - central) / max(1.4826 * mad, 1.0)


def detect_vital_anomalies(patient_id: str, records: list[dict],
                           minimum_history: int = 5, window: int = 12,
                           threshold: float = 4.5) -> list[Anomaly]:
    """Detecta variacoes do historico do mesmo paciente e metrica.

    Os limiares nao representam limites clinicos. Entradas devem estar
    ordenadas cronologicamente e conter observed_at, metric e value.
    """
    history: dict[tuple[str, str], list[float]] = {}
    results = []
    for record in sorted(records, key=lambda row: row["observed_at"]):
        metric, value = record["metric"], float(record["value"])
        source = str(record.get("source", "unspecified"))
        previous = history.setdefault((source, metric), [])
        reference = previous[-window:]
        if len(reference) >= minimum_history:
            score = robust_score(value, reference)
            if score >= threshold:
                source_suffix = "" if source == "unspecified" else "_" + source.rsplit(":", 1)[-1].upper()
                results.append(Anomaly(
                    patient_id, record["observed_at"], "vitals", "warning",
                    f"VITAL_{metric}{source_suffix}", f"Desvio estatistico em {metric}",
                    {"value": value, "baseline_median": median(reference),
                     "robust_score": round(score, 3), "threshold": threshold,
                     "source": source, "kind": "statistical_only"},
                ))
        previous.append(value)
    return results


def detect_prescription_changes(patient_id: str, records: list[dict],
                                max_ratio: float = 2.0) -> list[Anomaly]:
    """Sinaliza alteracoes abruptas de registros ficticios para revisao humana."""
    previous_by_medication: dict[str, dict] = {}
    alerts = []
    for row in sorted(records, key=lambda item: item["valid_from"]):
        medication = row["medication"].strip().casefold()
        previous = previous_by_medication.get(medication)
        if previous:
            same_unit = previous["unit"].strip().casefold() == row["unit"].strip().casefold()
            ratio = max(float(row["dose"]), float(previous["dose"])) / min(
                float(row["dose"]), float(previous["dose"])
            ) if same_unit else None
            frequency_changed = previous["frequency"] != row["frequency"]
            if not same_unit or (ratio is not None and ratio > max_ratio) or frequency_changed:
                alerts.append(Anomaly(
                    patient_id, row["valid_from"], "prescription", "warning",
                    f"RX_CHANGE_{medication.upper()}", "Alteracao de prescricao para revisao",
                    {"medication": row["medication"], "before": dict(previous),
                     "after": dict(row), "ratio": ratio, "kind": "administrative_review"},
                ))
        previous_by_medication[medication] = row
    return alerts


def detect_pose_outliers(patient_id: str, samples: list[dict],
                         angle_name: str = "left_knee", threshold: float = 4.5) -> list[Anomaly]:
    """Identifica frames fora do padrao proprio do video, sem classificar patologias."""
    history = []
    alerts = []
    for sample in samples:
        value = sample.get(angle_name)
        if value is None:
            continue
        if len(history) >= 5:
            score = robust_score(float(value), history[-12:])
            if score >= threshold:
                alerts.append(Anomaly(
                    patient_id, sample["observed_at"], "video", "warning",
                    (f"POSE_{angle_name.upper()}_" + str(sample["source"]).rsplit(":", 1)[-1].upper())
                    if sample.get("source") else f"POSE_{angle_name.upper()}",
                    "Movimento fora do padrao observado",
                    {"angle_degrees": round(value, 2), "robust_score": round(score, 3),
                     "source": sample.get("source", "unspecified"),
                     "kind": "motion_outlier"},
                ))
        history.append(float(value))
    return alerts


def fusion_alert(patient_id: str, events: list[Anomaly],
                 window_minutes: int = 30) -> Anomaly | None:
    """Agrega no mesmo caso demonstrativo, sem afirmar vinculo clinico causal."""
    events = [event for event in events if event.patient_id == patient_id]
    distinct_modalities = sorted({event.modality for event in events})
    if len(distinct_modalities) < 2:
        return None
    times = [datetime.fromisoformat(event.observed_at) for event in events]
    if (max(times) - min(times)).total_seconds() > window_minutes * 60:
        return None
    return Anomaly(
        patient_id, max(event.observed_at for event in events), "multimodal", "warning",
        "MULTIMODAL_REVIEW", "Eventos de diferentes modalidades exigem revisao conjunta",
        {"modalities": distinct_modalities, "event_codes": [event.code for event in events],
         "window_minutes": window_minutes,
         "kind": "synthetic_case_association"},
    )



def detect_movement_anomalies(patient_id: str, records: list[dict],
                              displacement_meters: float = 3.0,
                              inactivity_minutes: int = 30) -> list[Anomaly]:
    """Regras transparentes para trajetória *simulada* na internação.

    Coordenadas estão em metros de um cenário fictício, não são GPS nem
    limites clínicos. Ausência de mudança de posição não indica por si só risco.
    """
    from math import hypot

    observations = sorted(records, key=lambda row: row["observed_at"])
    events: list[Anomaly] = []
    last_moving_at: datetime | None = None
    inactivity_reported = False
    previous: dict | None = None
    for row in observations:
        current = datetime.fromisoformat(row["observed_at"])
        if current.tzinfo is None:
            raise ValueError("Data de movimento deve conter fuso horário")
        if previous is None:
            last_moving_at = current
        else:
            distance = hypot(float(row["x_m"]) - float(previous["x_m"]),
                             float(row["y_m"]) - float(previous["y_m"]))
            if distance > displacement_meters:
                events.append(Anomaly(
                    patient_id, row["observed_at"], "movement", "warning",
                    "MOVEMENT_DISPLACEMENT", "Deslocamento fora da referência simulada",
                    {"distance_m": round(distance, 3), "reference_m": displacement_meters,
                     "source": row.get("source", "synthetic"), "kind": "simulation_only"},
                ))
            if distance >= 0.5:
                last_moving_at = current
                inactivity_reported = False
            elif last_moving_at is not None:
                idle_minutes = (current - last_moving_at).total_seconds() / 60
                if idle_minutes >= inactivity_minutes and not inactivity_reported:
                    events.append(Anomaly(
                        patient_id, row["observed_at"], "movement", "info",
                        "MOVEMENT_INACTIVITY", "Período sem deslocamento no cenário simulado",
                        {"minutes": round(idle_minutes, 1),
                         "reference_minutes": inactivity_minutes,
                         "source": row.get("source", "synthetic"),
                         "kind": "simulation_only"},
                    ))
                    inactivity_reported = True
        previous = row
    return events
