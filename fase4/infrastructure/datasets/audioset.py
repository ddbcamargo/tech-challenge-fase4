"""Adaptador dos metadados AudioSet; nao sao consultas clinicas."""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioSetSegment:
    youtube_id: str
    start_seconds: float
    end_seconds: float
    label_ids: tuple[str, ...]


def read_segments(path: str | Path, limit: int | None = None) -> list[AudioSetSegment]:
    """Aceita balanced_train_segments.csv ou eval_segments.csv do Google AudioSet."""
    if limit is not None and limit <= 0:
        return []
    result = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        data_lines = (line for line in handle if line.strip() and not line.startswith("#"))
        for row in csv.reader(data_lines, skipinitialspace=True):
            if len(row) != 4:
                raise ValueError("Linha AudioSet invalida: esperado 4 campos")
            video_id, start, end, labels = row
            segment = AudioSetSegment(
                youtube_id=video_id.strip(), start_seconds=float(start),
                end_seconds=float(end),
                label_ids=tuple(label.strip() for label in labels.split(",") if label.strip()),
            )
            if (not math.isfinite(segment.start_seconds) or
                    not math.isfinite(segment.end_seconds) or
                    segment.start_seconds < 0 or segment.start_seconds >= segment.end_seconds):
                raise ValueError("Intervalo AudioSet invalido")
            result.append(segment)
            if limit is not None and len(result) >= limit:
                break
    return result


def read_label_map(path: str | Path) -> dict[str, str]:
    """Traduz IDs /m/... para classes acústicas oficiais em inglês."""
    with open(path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"index", "mid", "display_name"}.issubset(reader.fieldnames):
            raise ValueError("Arquivo de classes do AudioSet inválido")
        labels = {}
        for row in reader:
            label = (row["mid"] or "").strip()
            title = (row["display_name"] or "").strip()
            # A taxonomia oficial combina IDs /m/, /t/ e /g/.
            if not re.fullmatch(r"/[a-z0-9]+/[A-Za-z0-9_-]+", label) or not title or label in labels:
                raise ValueError("Classe duplicada ou inválida no AudioSet")
            labels[label] = title
        if not labels:
            raise ValueError("Arquivo de classes AudioSet vazio")
        return labels

