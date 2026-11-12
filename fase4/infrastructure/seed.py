"""Adaptador de dados ficticios; nao usa dados/codigo da Fase 3."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from .database import add_patient, add_prescription, initialize

FIRST_NAMES = ["Alex", "Bia", "Caio", "Dara", "Eli", "Fabi", "Gael", "Helo",
               "Ivo", "Jade", "Kai", "Lia", "Miro", "Nina", "Otto", "Pia",
               "Ravi", "Sora", "Téo", "Uma", "Vini", "Yara", "Zeca", "Luna", "Noel"]


def seed_patients(con, count: int = 25) -> int:
    """Cria ate 25 identidades totalmente sinteticas; chamada idempotente."""
    if not 0 <= count <= len(FIRST_NAMES):
        raise ValueError("count deve estar entre 0 e 25")
    initialize(con)
    created = 0
    for i in range(count):
        patient_id = f"TC4-P{i+1:03}"
        exists = con.execute("SELECT 1 FROM patients WHERE patient_id=?", (patient_id,)).fetchone()
        if exists:
            continue
        add_patient(con, patient_id, f"Pessoa Ficticia {FIRST_NAMES[i]}",
                    25 + (i * 7) % 60, ["Fisioterapia", "Observacao", "Enfermaria"][i % 3])
        created += 1
    return created


def seed_example_prescriptions(con) -> None:
    """Exemplos completamente inventados para detectar alteracoes, nao orientar tratamento."""
    patient = "TC4-P001"
    if not con.execute("SELECT 1 FROM patients WHERE patient_id=?", (patient,)).fetchone():
        raise ValueError("Execute seed_patients primeiro")
    if con.execute("SELECT 1 FROM prescriptions WHERE patient_id=?", (patient,)).fetchone():
        return
    baseline = datetime(2026, 1, 1, tzinfo=timezone.utc)
    add_prescription(con, patient, "Medicamento-X", 10, "unidade ficticia", "1x/dia", baseline.isoformat())
    add_prescription(con, patient, "Medicamento-X", 30, "unidade ficticia", "1x/dia",
                     (baseline + timedelta(days=1)).isoformat())



def seed_movement_examples(con) -> None:
    """Percurso inventado e reproduzível. Não corresponde a telemetria real."""
    from .database import add_movement
    patient = "TC4-P001"
    if not con.execute("SELECT 1 FROM patients WHERE patient_id=?", (patient,)).fetchone():
        return
    if con.execute("SELECT 1 FROM movement_samples WHERE patient_id=?", (patient,)).fetchone():
        return
    origin = datetime(2026, 1, 2, 9, tzinfo=timezone.utc)
    for step, (x, y) in enumerate([(0, 0), (0.1, 0), (0.1, 0.1), (0.2, 0.1),
                                   (0.1, 0.1), (0.2, 0.2), (8.0, 0.2),
                                   (8.0, 0.2), (8.1, 0.2)]):
        add_movement(con, patient,
                     (origin + timedelta(minutes=10 * step)).isoformat(),
                     x, y, "synthetic_ward")
