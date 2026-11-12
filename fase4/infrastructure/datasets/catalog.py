"""Aquisição controlada e validação de amostras oficiais para a demonstração.

Arquivos públicos permanecem em data/raw/ (fora do repositório). Este módulo
não baixa vídeos do YouTube nem acessa qualquer prontuário de pacientes.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from .audioset import read_label_map, read_segments
from .physionet import read_challenge2019_psv


@dataclass(frozen=True)
class OfficialFile:
    name: str
    url: str
    dataset: str
    license: str
    max_bytes: int = 10 * 1024 * 1024


# URLs de download direto publicadas pelas fontes, em versões fixadas.
OFFICIAL_FILES = (
    OfficialFile(
        "p100679.psv",
        "https://physionet.org/files/challenge-2019/1.0.0/training/training_setB/p100679.psv",
        "PhysioNet/CinC Challenge 2019 v1.0.0", "CC BY 4.0",
    ),
    OfficialFile(
        "balanced_train_segments.csv",
        "https://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/balanced_train_segments.csv",
        "Google AudioSet v1 (metadados de treinamento)", "CC BY 4.0",
    ),
    OfficialFile(
        "eval_segments.csv",
        "https://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/eval_segments.csv",
        "Google AudioSet v1 (metadados)", "CC BY 4.0",
    ),
    OfficialFile(
        "class_labels_indices.csv",
        "https://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv",
        "Google AudioSet v1 (metadados)", "CC BY 4.0",
    ),
)

MANIFEST_NAME = "manifest.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download_file(spec: OfficialFile, destination: Path) -> None:
    """Baixa com limite de tamanho e renomeia só após download completo."""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".download-",
                                         delete=False) as temporary:
            temp_path = Path(temporary.name)
            total = 0
            with urlopen(spec.url, timeout=30) as response:
                while chunk := response.read(64 * 1024):
                    total += len(chunk)
                    if total > spec.max_bytes:
                        raise ValueError(f"Download de {spec.name} excedeu o limite configurado")
                    temporary.write(chunk)
        os.replace(temp_path, destination)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _load_manifest(root: Path) -> dict:
    path = root / MANIFEST_NAME
    if not path.exists():
        return {"schema_version": 1, "files": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema_version") != 1 or not isinstance(value.get("files"), dict):
            raise ValueError("Estrutura do manifesto inválida")
        return value
    except (json.JSONDecodeError, AttributeError) as exc:
        raise ValueError("Manifesto inválido: revise data/raw/official/manifest.json") from exc


def _save_manifest(root: Path, manifest: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=root, prefix=".manifest-",
                                         encoding="utf-8", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, root / MANIFEST_NAME)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_datasets(root: str | Path) -> dict:
    """Confere formato, integridade e vínculo com a licença/fonte declaradas."""
    folder = Path(root)
    manifest = _load_manifest(folder)
    files = {}
    for spec in OFFICIAL_FILES:
        target = folder / spec.name
        entry = manifest["files"].get(spec.name)
        if not target.is_file():
            files[spec.name] = {"status": "missing", "dataset": spec.dataset}
            continue
        sha = file_sha256(target)
        if not entry:
            status = "untracked"
        elif (entry.get("sha256") != sha or entry.get("url") != spec.url or
              entry.get("license") != spec.license):
            status = "modified"
        else:
            status = "ok"
        files[spec.name] = {
            "status": status,
            "dataset": spec.dataset,
            "license": spec.license,
            "size_bytes": target.stat().st_size,
            "sha256": sha,
        }

    try:
        psv = folder / "p100679.psv"
        if psv.is_file():
            rows = read_challenge2019_psv(psv)
            files[psv.name]["hourly_rows"] = len(rows)
            files[psv.name]["valid_measurements"] = sum(
                value is not None for row in rows for key, value in row.items() if key != "hour"
            )

        labels_path = folder / "class_labels_indices.csv"
        labels = read_label_map(labels_path) if labels_path.is_file() else {}
        if labels:
            files[labels_path.name]["classes"] = len(labels)

        for name in ("balanced_train_segments.csv", "eval_segments.csv"):
            segments_path = folder / name
            if segments_path.is_file():
                segments = read_segments(segments_path)
                if not segments:
                    raise ValueError("AudioSet sem segmentos")
                files[name]["segments"] = len(segments)
                if labels:
                    unknown = {mid for segment in segments for mid in segment.label_ids} - labels.keys()
                    if unknown:
                        raise ValueError(f"AudioSet tem {len(unknown)} classes sem mapeamento")
                    speech_ids = {mid for mid, title in labels.items() if "speech" in title.lower()}
                    files[name]["segments_with_speech_labels"] = sum(
                        bool(speech_ids.intersection(segment.label_ids)) for segment in segments
                    )
    except (ValueError, OSError) as exc:
        return {"ready": False, "files": files, "validation_error": str(exc)}

    return {"ready": all(item["status"] == "ok" for item in files.values()),
            "files": files}


def prepare_datasets(root: str | Path) -> dict:
    """Um PSV + três CSVs oficiais, com hash e proveniência; idempotente."""
    folder = Path(root)
    folder.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(folder)
    for spec in OFFICIAL_FILES:
        target = folder / spec.name
        known = manifest["files"].get(spec.name)
        if target.exists():
            if not target.is_file() or not known or known.get("sha256") != file_sha256(target) or known.get("url") != spec.url:
                raise ValueError(f"{spec.name} já existe sem procedência válida; use outro --dir")
            continue
        _download_file(spec, target)
        manifest["files"][spec.name] = {
            "url": spec.url, "dataset": spec.dataset, "license": spec.license,
            "sha256": file_sha256(target), "size_bytes": target.stat().st_size,
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _save_manifest(folder, manifest)
    return validate_datasets(folder)


class OfficialDatasets:
    """Adaptador para o protocolo DatasetProvider da camada de aplicação."""

    def prepare(self, root: str | Path) -> dict:
        return prepare_datasets(root)

    def validate(self, root: str | Path) -> dict:
        return validate_datasets(root)
