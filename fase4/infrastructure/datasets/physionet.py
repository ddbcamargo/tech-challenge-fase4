"""Adaptador PhysioNet/CinC 2019 (PSV, sem download automatico)."""

from __future__ import annotations

import csv
import hashlib
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

VITAL_COLUMNS = ("HR", "O2Sat", "Temp", "SBP", "MAP", "DBP", "Resp")


def read_challenge2019_psv(path: str | Path) -> list[dict]:
    """Retorna os valores numéricos, mantendo NaN como ausente."""
    with open(path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="|")
        required = {"HR", "O2Sat", "SBP", "DBP", "Resp"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Arquivo nao corresponde ao formato PhysioNet Challenge 2019")
        result = []
        for hour, row in enumerate(reader):
            parsed = {"hour": hour}
            for column in VITAL_COLUMNS:
                raw = row.get(column, "").strip()
                if raw:
                    try:
                        value = float(raw)
                    except ValueError as exc:
                        raise ValueError(f"Valor invalido na coluna {column}, linha {hour+2}") from exc
                    parsed[column] = value if math.isfinite(value) else None
                else:
                    parsed[column] = None
            result.append(parsed)
        if not result:
            raise ValueError("Arquivo PhysioNet sem linhas de medições")
        return result


def import_psv(con, path: str | Path, synthetic_patient_id: str,
               start_at: datetime | None = None) -> int:
    """Vincula uma serie publica a paciente ficticio *somente* para replay academico.

    A vinculacao nao implica que o paciente ficticio seja o paciente real da fonte.
    """
    if not con.execute("SELECT 1 FROM patients WHERE patient_id=?", (synthetic_patient_id,)).fetchone():
        raise ValueError("Paciente ficticio inexistente")
    start = start_at or datetime(2026, 1, 1, tzinfo=timezone.utc)
    if start.tzinfo is None:
        raise ValueError("start_at deve conter timezone")
    rows = read_challenge2019_psv(path)
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    # Cada série pública mantém a própria identidade de origem, mesmo quando
    # duas fontes são reproduzidas no mesmo caso fictício.
    source = f"physionet-challenge-2019-replay:{digest}"
    measures = []
    for row in rows:
        observed_at = (start + timedelta(hours=row["hour"])).isoformat()
        for metric in VITAL_COLUMNS:
            value = row[metric]
            if value is not None:
                measures.append((synthetic_patient_id, observed_at, metric, value,
                                 source))
    before = con.total_changes
    con.executemany(
        "INSERT OR IGNORE INTO vital_signs(patient_id, observed_at, metric, value, source) "
        "VALUES (?, ?, ?, ?, ?)", measures)
    con.commit()
    return con.total_changes - before

