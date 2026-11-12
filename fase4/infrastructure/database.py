"""Adaptador SQLite independente dos projetos das fases anteriores."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def default_db_path() -> str:
    return os.environ.get("FASE4_DB_PATH", "data/fase4.sqlite3")


class AutoClosingConnection(sqlite3.Connection):
    """Fecha o SQLite ao sair do `with`, inclusive quando ocorre exceção.

    O contexto padrão de sqlite3.Connection faz commit/rollback, mas *não*
    fecha a conexão. No Windows isso mantém bancos temporários bloqueados.
    Fora do `with`, quem chama `connect()` continua responsável por `close()`.
    """

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    location = str(path or default_db_path())
    if location != ":memory:":
        Path(location).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(location, factory=AutoClosingConnection)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER NOT NULL CHECK(age BETWEEN 0 AND 120),
    ward TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vital_signs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    observed_at TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    source TEXT NOT NULL,
    UNIQUE(patient_id, observed_at, metric, source)
);
CREATE TABLE IF NOT EXISTS prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    medication TEXT NOT NULL,
    dose REAL NOT NULL CHECK(dose > 0),
    unit TEXT NOT NULL,
    frequency TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'synthetic'
);
CREATE TABLE IF NOT EXISTS media_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    modality TEXT NOT NULL CHECK(modality IN ('audio', 'video')),
    occurred_at TEXT NOT NULL,
    source_name TEXT NOT NULL,
    result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    observed_at TEXT NOT NULL,
    modality TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('info', 'warning', 'critical')),
    code TEXT NOT NULL,
    description TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_review'
      CHECK(status IN ('pending_review', 'reviewed', 'dismissed')),
    recorded_at TEXT NOT NULL DEFAULT '',
    UNIQUE(patient_id, observed_at, modality, code)
);
CREATE TABLE IF NOT EXISTS movement_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    observed_at TEXT NOT NULL,
    x_m REAL NOT NULL,
    y_m REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'synthetic_ward',
    UNIQUE(patient_id, observed_at, source)
);
CREATE INDEX IF NOT EXISTS idx_movement_patient_time ON movement_samples(patient_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_vitals_patient_time ON vital_signs(patient_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_alerts_patient_time ON alerts(patient_id, observed_at);
"""


def initialize(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    # Migração idempotente de bancos da v0.8.x, sem apagar histórico.
    alert_columns = {row["name"] for row in con.execute("PRAGMA table_info(alerts)")}
    if "recorded_at" not in alert_columns:
        con.execute("ALTER TABLE alerts ADD COLUMN recorded_at TEXT NOT NULL DEFAULT ''")
        # Não correlacionar retroativamente alertas de versões anteriores.
        con.execute("UPDATE alerts SET recorded_at=observed_at WHERE recorded_at='' ")
    con.commit()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_patient(con: sqlite3.Connection, patient_id: str, name: str, age: int, ward: str) -> None:
    con.execute(
        "INSERT INTO patients(patient_id, name, age, ward, created_at) VALUES (?, ?, ?, ?, ?)",
        (patient_id, name, age, ward, utc_now()),
    )
    con.commit()


def add_vital(con: sqlite3.Connection, patient_id: str, observed_at: str,
              metric: str, value: float, source: str) -> None:
    con.execute(
        "INSERT OR IGNORE INTO vital_signs(patient_id, observed_at, metric, value, source) "
        "VALUES (?, ?, ?, ?, ?)",
        (patient_id, observed_at, metric, value, source),
    )
    con.commit()


def add_prescription(con: sqlite3.Connection, patient_id: str, medication: str,
                     dose: float, unit: str, frequency: str, valid_from: str) -> None:
    con.execute(
        "INSERT INTO prescriptions(patient_id, medication, dose, unit, frequency, valid_from) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (patient_id, medication, dose, unit, frequency, valid_from),
    )
    con.commit()


def add_alert(con: sqlite3.Connection, patient_id: str, observed_at: str,
              modality: str, severity: str, code: str, description: str,
              evidence: dict) -> None:
    con.execute(
        "INSERT OR IGNORE INTO alerts(patient_id, observed_at, modality, severity, code, "
        "description, evidence_json, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (patient_id, observed_at, modality, severity, code, description,
         json.dumps(evidence, ensure_ascii=False, sort_keys=True), utc_now()),
    )
    con.commit()


def add_media_event(con: sqlite3.Connection, patient_id: str, modality: str,
                    occurred_at: str, source_name: str, result: dict) -> int:
    cursor = con.execute(
        "INSERT INTO media_events(patient_id, modality, occurred_at, source_name, result_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (patient_id, modality, occurred_at, source_name,
         json.dumps(result, ensure_ascii=False, sort_keys=True)),
    )
    con.commit()
    return int(cursor.lastrowid)


def list_patients(con: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in con.execute("SELECT * FROM patients ORDER BY patient_id")]


def list_alerts(con: sqlite3.Connection, patient_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM alerts"
    params: tuple[str, ...] = ()
    if patient_id:
        query += " WHERE patient_id = ?"
        params = (patient_id,)
    query += " ORDER BY observed_at DESC, id DESC"
    return [dict(row) for row in con.execute(query, params)]


def review_alert(con: sqlite3.Connection, alert_id: int, patient_id: str, status: str) -> bool:
    """Somente alertas ainda pendentes podem receber decisão humana."""
    if status not in {"reviewed", "dismissed"}:
        raise ValueError("Status de revisão inválido")
    changed = con.execute(
        "UPDATE alerts SET status=? WHERE id=? AND patient_id=? AND status='pending_review'",
        (status, alert_id, patient_id),
    ).rowcount
    con.commit()
    return changed == 1


def list_vitals(con: sqlite3.Connection, patient_id: str) -> list[dict]:
    return [dict(row) for row in con.execute(
        "SELECT * FROM vital_signs WHERE patient_id = ? ORDER BY observed_at, id", (patient_id,)
    )]



def list_media_events(con: sqlite3.Connection, patient_id: str,
                      modality: str = "audio", limit: int = 20) -> list[dict]:
    """Histórico limitado, com resultado interpretado, sem acessar os arquivos de áudio."""
    if modality not in {"audio", "video"}:
        raise ValueError("Modalidade inválida")
    if not 1 <= limit <= 100:
        raise ValueError("Limit deve estar entre 1 e 100")
    rows = con.execute(
        "SELECT id, patient_id, modality, occurred_at, source_name, result_json "
        "FROM media_events WHERE patient_id=? AND modality=? ORDER BY id DESC LIMIT ?",
        (patient_id, modality, limit),
    )
    return [
        {"id": row["id"], "patient_id": row["patient_id"],
         "modality": row["modality"], "occurred_at": row["occurred_at"],
         "source_name": row["source_name"], "result": json.loads(row["result_json"])}
        for row in rows
    ]


def add_movement(con: sqlite3.Connection, patient_id: str, observed_at: str,
                 x_m: float, y_m: float, source: str = "synthetic_ward") -> None:
    con.execute(
        "INSERT OR IGNORE INTO movement_samples(patient_id, observed_at, x_m, y_m, source) "
        "VALUES (?, ?, ?, ?, ?)", (patient_id, observed_at, x_m, y_m, source),
    )
    con.commit()


def list_movement(con: sqlite3.Connection, patient_id: str) -> list[dict]:
    return [dict(row) for row in con.execute(
        "SELECT patient_id, observed_at, x_m, y_m, source FROM movement_samples "
        "WHERE patient_id=? ORDER BY observed_at", (patient_id,),
    )]
