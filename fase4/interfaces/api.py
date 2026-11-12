"""Interface FastAPI: delega consultas para a mesma aplicação do dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from ..container import build_application


@asynccontextmanager
async def lifespan(_: FastAPI):
    build_application().bootstrap()
    yield


app = FastAPI(title="Tech Challenge Fase 4 — API acadêmica", version="0.9.0",
              lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "clinical_use": False}


@app.get("/patients")
def patients() -> list[dict]:
    return build_application().patients()


def _require_patient(patient_id: str):
    service = build_application()
    if not any(row["patient_id"] == patient_id for row in service.patients()):
        raise HTTPException(404, "Paciente fictício não encontrado")
    return service


@app.get("/patients/{patient_id}/vitals")
def patient_vitals(patient_id: str) -> list[dict]:
    return _require_patient(patient_id).vitals(patient_id)


@app.get("/patients/{patient_id}/alerts")
def patient_alerts(patient_id: str) -> list[dict]:
    return _require_patient(patient_id).alerts(patient_id)



@app.get("/patients/{patient_id}/media-events")
def patient_media_events(patient_id: str, modality: str = "audio", limit: int = 20) -> list[dict]:
    try:
        return _require_patient(patient_id).media_events(patient_id, modality, limit)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@app.get("/patients/{patient_id}/movement")
def patient_movement(patient_id: str) -> list[dict]:
    return _require_patient(patient_id).movements(patient_id)


@app.post("/patients/{patient_id}/scan")
def patient_scan(patient_id: str) -> dict:
    return _require_patient(patient_id).scan_monitoring(patient_id)


@app.post("/patients/{patient_id}/correlate")
def patient_correlate(patient_id: str) -> dict:
    result = _require_patient(patient_id).correlate_alerts(patient_id)
    return {"created": result is not None,
            "code": result.code if result is not None else None,
            "clinical_assessment": False}
