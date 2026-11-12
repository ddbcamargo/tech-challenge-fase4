"""Curadoria rastreável de trechos do Google AudioSet (sem baixar vídeos).

A fonte fornece *índices* dos trechos. Os WAVs devem ser obtidos pelo usuário
com autorização e corresponder exatamente aos trechos selecionados. O nome
não prova a origem: a atestação é explícita e registrada como não verificada.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .audioset import read_label_map, read_segments
from .catalog import file_sha256, validate_datasets
from ..voice_features import read_voice_wav

_ALLOWED_SPLITS = {
    "balanced_train": "balanced_train_segments.csv",
    "eval": "eval_segments.csv",
}
_CLIP_ID = re.compile(r"^[A-Za-z0-9_-]{11}_[0-9]{6,9}_[0-9]{6,9}$")
_MIN_REFERENCE = 12
_MAX_REFERENCE = 100


def _clip_id(youtube_id: str, start: float, end: float) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", youtube_id):
        raise ValueError("Identificador de vídeo AudioSet inválido")
    identifier = f"{youtube_id}_{round(start * 1000):06d}_{round(end * 1000):06d}"
    if not _CLIP_ID.fullmatch(identifier):
        raise ValueError("Identificador de trecho AudioSet inválido")
    return identifier


class LocalAudioSetSamples:
    def __init__(self, official_root: str | Path = "data/raw/official",
                 workspace: str | Path = "data/raw/audioset") -> None:
        self.official_root = Path(official_root)
        self.workspace = Path(workspace)
        self.selection_path = self.workspace / "selection.json"
        self.clips_root = self.workspace / "clips"

    def select(self, label: str = "Speech", split: str = "balanced_train",
               limit: int = 24) -> dict:
        """Seleciona registros da fonte oficial; não gera áudio fictício."""
        if split not in _ALLOWED_SPLITS:
            raise ValueError("Split permitido: balanced_train ou eval")
        if not 1 <= limit <= _MAX_REFERENCE:
            raise ValueError("Selecione de 1 a 100 segmentos por vez")
        report = validate_datasets(self.official_root)
        if not report["ready"]:
            raise ValueError("Prepare e valide as bases oficiais antes de selecionar trechos")
        labels = read_label_map(self.official_root / "class_labels_indices.csv")
        exact = [mid for mid, title in labels.items() if title.casefold() == label.strip().casefold()]
        if len(exact) != 1:
            raise ValueError("Rótulo não encontrado ou ambíguo no catálogo oficial do AudioSet")
        label_id = exact[0]
        filename = _ALLOWED_SPLITS[split]
        segments = read_segments(self.official_root / filename)
        selected = []
        used_video_ids = set()
        for segment in segments:
            if label_id not in segment.label_ids or segment.youtube_id in used_video_ids:
                continue
            used_video_ids.add(segment.youtube_id)
            clip_id = _clip_id(segment.youtube_id, segment.start_seconds, segment.end_seconds)
            selected.append({
                "id": clip_id,
                "youtube_id": segment.youtube_id,
                "start_seconds": segment.start_seconds,
                "end_seconds": segment.end_seconds,
                "label_ids": list(segment.label_ids),
                "label_names": [labels.get(mid, mid) for mid in segment.label_ids],
                "filename": f"{clip_id}.wav",
                "source_url": (f"https://www.youtube.com/watch?v={segment.youtube_id}"
                               f"&t={int(segment.start_seconds)}s"),
            })
            if len(selected) == limit:
                break
        if not selected:
            raise ValueError("Não há segmentos com esse rótulo no split escolhido")
        self.workspace.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 1, "dataset": "Google AudioSet v1",
            "split": split, "split_filename": filename,
            "split_sha256": file_sha256(self.official_root / filename),
            "class_map_sha256": file_sha256(self.official_root / "class_labels_indices.csv"),
            "label": labels[label_id], "label_id": label_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "clips": selected,
            "provenance_note": (
                "O AudioSet fornece os índices e rótulos. O conteúdo de WAVs "
                "importados pelo usuário NÃO é verificado automaticamente contra o YouTube."
            ),
        }
        # Não sobrescrever silenciosamente uma seleção já usada.
        if self.selection_path.exists():
            old = self._read()
            if any((self.clips_root / item["filename"]).exists() for item in old["clips"]):
                raise ValueError("Há WAVs na seleção atual. Remova/mova os WAVs antes de selecionar outro conjunto")
        self.selection_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.status()

    def _read(self) -> dict:
        if not self.selection_path.is_file():
            raise ValueError("Seleção AudioSet ausente. Execute audioset-select primeiro")
        try:
            manifest = json.loads(self.selection_path.read_text(encoding="utf-8"))
            if (manifest.get("schema_version") != 1 or
                    manifest.get("split") not in _ALLOWED_SPLITS or
                    not isinstance(manifest.get("clips"), list)):
                raise ValueError("Seleção AudioSet malformada")
            filename = _ALLOWED_SPLITS[manifest["split"]]
            if manifest["split_filename"] != filename:
                raise ValueError("Split AudioSet inconsistente")
            for name, digest in ((filename, "split_sha256"),
                                 ("class_labels_indices.csv", "class_map_sha256")):
                path = self.official_root / name
                if not path.is_file() or file_sha256(path) != manifest[digest]:
                    raise ValueError(f"Arquivo oficial {name} alterado; refaça a seleção")
            valid_rows = {
                _clip_id(row.youtube_id, row.start_seconds, row.end_seconds): row
                for row in read_segments(self.official_root / filename)
            }
            if len({row["id"] for row in manifest["clips"]}) != len(manifest["clips"]):
                raise ValueError("Seleção contém trechos duplicados")
            label_map = read_label_map(self.official_root / "class_labels_indices.csv")
            if label_map.get(manifest["label_id"]) != manifest["label"]:
                raise ValueError("Rótulo da seleção não corresponde ao catálogo oficial")
            for item in manifest["clips"]:
                clip_id = item["id"]
                original = valid_rows.get(clip_id)
                if (not _CLIP_ID.fullmatch(clip_id) or original is None or
                        manifest["label_id"] not in original.label_ids or
                        item["filename"] != f"{clip_id}.wav"):
                    raise ValueError("Trecho não corresponde aos metadados oficiais")
            return manifest
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Seleção AudioSet inválida; refaça a seleção") from exc

    def status(self) -> dict:
        if not self.selection_path.is_file():
            return {"ready": False, "dataset": "Google AudioSet v1",
                    "selected": 0, "available": 0, "items": []}
        manifest = self._read()
        items = []
        for item in manifest["clips"]:
            path = self.clips_root / item["filename"]
            items.append({**item, "wav_available": path.is_file()})
        return {
            "ready": True, "dataset": manifest["dataset"],
            "label": manifest["label"], "split": manifest["split"],
            "selected": len(items),
            "available": sum(row["wav_available"] for row in items),
            "missing": sum(not row["wav_available"] for row in items),
            "items": items,
            "license_note": "Confira os direitos de uso do áudio de cada vídeo antes de importar",
            "source_verified": False,
        }

    def import_clip(self, clip_id: str, path: str | Path) -> dict:
        """Cadastra WAV fornecido pelo usuário, com validação técnica e atestação externa."""
        manifest = self._read()
        item = next((x for x in manifest["clips"] if x["id"] == clip_id), None)
        if item is None:
            raise ValueError("Trecho não pertence à seleção oficial")
        samples, rate = read_voice_wav(path)
        duration = len(samples) / rate
        if abs(duration - (item["end_seconds"] - item["start_seconds"])) > 0.25:
            raise ValueError("Duração do WAV não corresponde ao trecho AudioSet selecionado")
        self.clips_root.mkdir(parents=True, exist_ok=True)
        target = self.clips_root / item["filename"]
        if target.exists():
            raise ValueError("Esse trecho já possui WAV; não será sobrescrito")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.clips_root, prefix=".clip-", delete=False) as handle:
                temporary = Path(handle.name)
                with Path(path).open("rb") as source:
                    shutil.copyfileobj(source, handle)
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return {"id": clip_id, "path": str(target), "sha256": file_sha256(target),
                "duration_seconds": round(duration, 3), "source_verified": False,
                "warning": "A correspondência real com o vídeo precisa ser conferida pelo pesquisador"}

    def training_references(self) -> tuple[list[Path], dict]:
        manifest = self._read()
        if manifest["split"] != "balanced_train" or manifest["label"] != "Speech":
            raise ValueError("Treine a referência vocal somente com AudioSet balanced_train / Speech")
        available = [
            self.clips_root / item["filename"] for item in manifest["clips"]
            if (self.clips_root / item["filename"]).is_file()
        ]
        if not _MIN_REFERENCE <= len(available) <= _MAX_REFERENCE:
            raise ValueError(f"Necessários {_MIN_REFERENCE} a {_MAX_REFERENCE} WAVs AudioSet de fala")
        intervals = {item["filename"]: item["end_seconds"] - item["start_seconds"]
                     for item in manifest["clips"]}
        for path in available:
            samples, rate = read_voice_wav(path)
            if abs(len(samples) / rate - intervals[path.name]) > 0.25:
                raise ValueError("WAV de referência não corresponde à duração do trecho AudioSet")
        metadata = {
            "dataset": "Google AudioSet v1", "split": manifest["split"],
            "label": manifest["label"], "selection_sha256": file_sha256(self.selection_path),
            "files": [{"name": path.name, "sha256": file_sha256(path)} for path in available],
            "source_verified": False,
        }
        return available, metadata
