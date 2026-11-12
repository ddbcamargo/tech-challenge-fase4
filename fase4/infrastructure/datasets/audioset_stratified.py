"""Curadoria estratificada do AudioSet: metadados oficiais, sem obter vídeos.

O índice AudioSet é multirrótulo. A categoria atribuída aqui serve para organizar
as REFERÊNCIAS acústicas; não estabelece diagnóstico nem verificação de conteúdo.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .audioset import read_label_map, read_segments
from .audioset_samples import _clip_id, _CLIP_ID
from .catalog import file_sha256, validate_datasets
from ..voice_features import read_voice_wav

TRAIN_QUOTAS = {"Speech": 24, "Breathing": 16, "Cough": 16, "Wheeze": 16, "Silence": 8}
EVAL_QUOTAS = {"Speech": 8, "Breathing": 6, "Cough": 6, "Wheeze": 6, "Silence": 6}
TRAINABLE_CATEGORIES = ("Speech", "Breathing", "Cough", "Wheeze")
SPLITS = {"balanced_train": "balanced_train_segments.csv", "eval": "eval_segments.csv"}
MIN_REFERENCE = 12
MAX_REFERENCE = 100


def _rank(seed: int, split: str, category: str, clip_id: str) -> str:
    """Hash estável para sorteio reprodutível, independente da ordem do CSV."""
    return hashlib.sha256(f"{seed}|{split}|{category}|{clip_id}".encode()).hexdigest()


class StratifiedAudioSetSamples:
    def __init__(self, official_root: str | Path = "data/raw/official",
                 workspace: str | Path = "data/raw/audioset") -> None:
        self.official_root = Path(official_root)
        self.workspace = Path(workspace)
        self.selection_path = self.workspace / "stratified_selection.json"
        self.clips_root = self.workspace / "stratified_clips"

    def select(self, seed: int = 42, train_quotas: dict | None = None,
               eval_quotas: dict | None = None) -> dict:
        """Seleciona por classe sem repetir vídeo nos conjuntos de treino/avaliação."""
        quotas = {"balanced_train": dict(TRAIN_QUOTAS if train_quotas is None else train_quotas),
                  "eval": dict(EVAL_QUOTAS if eval_quotas is None else eval_quotas)}
        if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= 2**32 - 1:
            raise ValueError("A semente deve ser um inteiro entre 0 e 2^32-1")
        for split, desired in quotas.items():
            if (not desired or set(desired) - set(TRAIN_QUOTAS) or
                    any(type(count) is not int or not 0 <= count <= 100 for count in desired.values()) or
                    not any(desired.values())):
                raise ValueError(f"Cotas inválidas para {split}")
        if not validate_datasets(self.official_root)["ready"]:
            raise ValueError("Prepare/valide os arquivos oficiais antes da curadoria")
        if self.selection_path.exists():
            previous = self._read()
            if any(self._path(item).exists() for item in previous["clips"]):
                raise ValueError("Seleção estratificada possui WAVs importados; preserve-os antes de refazer a seleção")
        labels = read_label_map(self.official_root / "class_labels_indices.csv")
        by_name = {name: mid for mid, name in labels.items()}
        names = set(quotas["balanced_train"]) | set(quotas["eval"])
        absent = sorted(names - by_name.keys())
        if absent:
            raise ValueError(f"Rótulos ausentes do catálogo oficial: {', '.join(absent)}")
        mids = {name: by_name[name] for name in names}
        selected: list[dict] = []
        used_videos: set[str] = set()
        shortages: list[dict] = []
        for split in ("balanced_train", "eval"):
            segments = read_segments(self.official_root / SPLITS[split])
            for category, requested in quotas[split].items():
                if requested == 0:
                    continue
                mid = mids[category]
                candidates = [item for item in segments if mid in item.label_ids and
                              item.youtube_id not in used_videos]
                # Priorizar gravações menos ambíguas entre as categorias de interesse;
                # não descartar rótulos adicionais de ambiente ou de outras categorias.
                candidates.sort(key=lambda item: (
                    sum(other in item.label_ids for other in mids.values() if other != mid),
                    _rank(seed, split, category,
                          _clip_id(item.youtube_id, item.start_seconds, item.end_seconds)),
                ))
                count = 0
                for segment in candidates:
                    if segment.youtube_id in used_videos:
                        continue
                    clip_id = _clip_id(segment.youtube_id, segment.start_seconds, segment.end_seconds)
                    used_videos.add(segment.youtube_id)
                    selected.append({
                        "id": clip_id, "youtube_id": segment.youtube_id,
                        "start_seconds": segment.start_seconds,
                        "end_seconds": segment.end_seconds,
                        "label_ids": list(segment.label_ids),
                        "label_names": [labels.get(value, value) for value in segment.label_ids],
                        "category": category, "category_mid": mid, "split": split,
                        "filename": f"{clip_id}.wav",
                        "source_url": (f"https://www.youtube.com/watch?v={segment.youtube_id}"
                                       f"&t={int(segment.start_seconds)}s"),
                    })
                    count += 1
                    if count >= requested:
                        break
                if count < requested:
                    shortages.append({"split": split, "category": category,
                                      "requested": requested, "selected": count})
        self.workspace.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 2, "dataset": "Google AudioSet v1", "seed": seed,
            "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "split_sha256": {key: file_sha256(self.official_root / filename)
                             for key, filename in SPLITS.items()},
            "class_map_sha256": file_sha256(self.official_root / "class_labels_indices.csv"),
            "quotas": quotas, "clips": selected, "shortages": shortages,
            "source_verified": False,
            "provenance_note": "WAVs fornecidos manualmente; correspondência com YouTube não verificada automaticamente",
        }
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=self.workspace, encoding="utf-8",
                                             prefix=".selection-", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(manifest, handle, ensure_ascii=False, indent=2)
            os.replace(temporary, self.selection_path)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        return self.status()

    def _path(self, item: dict) -> Path:
        return self.clips_root / item["split"] / item["category"] / item["filename"]

    def _read(self) -> dict:
        if not self.selection_path.is_file():
            raise ValueError("Seleção estratificada ausente; execute audioset-curate")
        try:
            manifest = json.loads(self.selection_path.read_text(encoding="utf-8"))
            if (manifest.get("schema_version") != 2 or
                    not isinstance(manifest.get("clips"), list) or
                    not isinstance(manifest.get("quotas"), dict)):
                raise ValueError("Manifesto de curadoria malformado")
            official = read_label_map(self.official_root / "class_labels_indices.csv")
            if file_sha256(self.official_root / "class_labels_indices.csv") != manifest["class_map_sha256"]:
                raise ValueError("Rótulos oficiais alterados")
            actual = {}
            for split, filename in SPLITS.items():
                if file_sha256(self.official_root / filename) != manifest["split_sha256"][split]:
                    raise ValueError(f"CSV oficial {filename} alterado")
                actual[split] = {
                    _clip_id(item.youtube_id, item.start_seconds, item.end_seconds): item
                    for item in read_segments(self.official_root / filename)
                }
            used_videos = set()
            for item in manifest["clips"]:
                clip_id = item["id"]
                split, category = item["split"], item["category"]
                if (split not in SPLITS or category not in TRAIN_QUOTAS or
                        not isinstance(clip_id, str) or not _CLIP_ID.fullmatch(clip_id) or
                        item["filename"] != f"{clip_id}.wav" or
                        clip_id not in actual[split] or
                        official.get(item["category_mid"]) != category or
                        item["category_mid"] not in actual[split][clip_id].label_ids or
                        item["youtube_id"] != actual[split][clip_id].youtube_id or
                        item["youtube_id"] in used_videos or
                        set(item["label_ids"]) != set(actual[split][clip_id].label_ids)):
                    raise ValueError("Trecho curado não corresponde aos metadados oficiais")
                used_videos.add(item["youtube_id"])
            return manifest
        except (OSError, KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
            raise ValueError("Manifesto estratificado inválido; revise os CSVs oficiais") from exc

    def status(self) -> dict:
        if not self.selection_path.is_file():
            return {"ready": False, "selected": 0, "available": 0, "missing": 0,
                    "items": [], "by_category": [], "shortages": [], "source_verified": False}
        manifest = self._read()
        items = [{**item, "wav_available": self._path(item).is_file()}
                 for item in manifest["clips"]]
        counters: dict[tuple[str, str], dict] = {}
        for item in items:
            key = (item["split"], item["category"])
            row = counters.setdefault(key, {"split": key[0], "category": key[1],
                                           "selected": 0, "available": 0})
            row["selected"] += 1
            row["available"] += int(item["wav_available"])
        return {"ready": True, "dataset": manifest["dataset"],
                "selected": len(items),
                "available": sum(item["wav_available"] for item in items),
                "missing": sum(not item["wav_available"] for item in items),
                "seed": manifest["seed"], "by_category": list(counters.values()),
                "shortages": manifest["shortages"], "items": items,
                "source_verified": False}

    def import_clip(self, clip_id: str, path: str | Path) -> dict:
        manifest = self._read()
        item = next((x for x in manifest["clips"] if x["id"] == clip_id), None)
        if item is None:
            raise ValueError("ID não pertence à seleção estratificada")
        samples, sample_rate = read_voice_wav(path)
        duration = len(samples) / sample_rate
        if abs(duration - (item["end_seconds"] - item["start_seconds"])) > 0.25:
            raise ValueError("Duração WAV incompatível com o intervalo do AudioSet")
        target = self._path(item)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError("Já existe WAV para esse ID; não será sobrescrito")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".import-", delete=False) as handle:
                temporary = Path(handle.name)
                with Path(path).open("rb") as reader:
                    shutil.copyfileobj(reader, handle)
            os.replace(temporary, target)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        return {"id": clip_id, "split": item["split"], "category": item["category"],
                "sha256": file_sha256(target), "source_verified": False}

    def references(self, category: str, split: str = "balanced_train") -> tuple[list[Path], dict]:
        if category not in TRAIN_QUOTAS:
            raise ValueError("Categoria não suportada na curadoria")
        if split not in SPLITS:
            raise ValueError("Split inválido")
        manifest = self._read()
        items = [item for item in manifest["clips"] if item["category"] == category
                 and item["split"] == split and self._path(item).is_file()]
        if split == "balanced_train" and category in TRAINABLE_CATEGORIES and len(items) < MIN_REFERENCE:
            raise ValueError(f"Importe pelo menos {MIN_REFERENCE} WAVs oficiais de {category} para treinamento")
        if split == "balanced_train" and category not in TRAINABLE_CATEGORIES:
            raise ValueError("Silence é controle acústico, não referência vocal de treinamento")
        if len(items) > MAX_REFERENCE:
            raise ValueError("Excesso de referências: máximo 100 por categoria")
        paths = [self._path(item) for item in items]
        for path, item in zip(paths, items):
            audio, sr = read_voice_wav(path)
            if abs(len(audio) / sr - (item["end_seconds"] - item["start_seconds"])) > 0.25:
                raise ValueError("WAV importado teve duração alterada")
        provenance = {"dataset": manifest["dataset"], "split": split, "label": category,
                      "curation": "stratified", "seed": manifest["seed"],
                      "selection_sha256": file_sha256(self.selection_path),
                      "source_verified": False,
                      "files": [{"name": path.name, "sha256": file_sha256(path),
                                 "youtube_id": item["youtube_id"]}
                                for path, item in zip(paths, items)]}
        return paths, provenance
