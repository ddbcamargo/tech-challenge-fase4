"""Aquisição explícita de trechos AudioSet permitidos e conversão a WAV.

O índice AudioSet não autoriza, por si só, downloads de vídeos. O modo
online exige confirmação de autorização pelo YouTube e titulares.
Não tenta burlar autenticação, DRM, quotas ou restrições de acesso.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .audioset_stratified import SPLITS, TRAIN_QUOTAS, StratifiedAudioSetSamples


def resolve_ffmpeg_exe() -> str:
    """Localiza o FFmpeg do wheel imageio-ffmpeg ou uma instalação do sistema.

    O arquivo executável no wheel não é incluído automaticamente no PATH.
    Evita dependência de instalação global no Windows/Git Bash.
    """
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError):
        executable = shutil.which("ffmpeg")
        if executable:
            return executable
        raise ValueError(
            'FFmpeg indisponível: execute python -m pip install -e ".[all,test,downloader]"'
        ) from None


class AuthorizedAudioSetFetcher:
    """Usa o manifesto oficial da curadoria e só importa WAVs validados."""

    def __init__(self, samples: StratifiedAudioSetSamples) -> None:
        self.samples = samples

    def plan(self, category: str = "Speech", split: str = "balanced_train",
             limit: int = 24) -> dict:
        if category not in TRAIN_QUOTAS and category != "all":
            raise ValueError("Categoria não suportada")
        if split not in SPLITS:
            raise ValueError("Split inválido")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Use um limite de 1 a 100 trechos por execução")
        status = self.samples.status()
        if not status["ready"]:
            raise ValueError("Execute audioset-curate antes de preparar os downloads")
        rows = [item for item in status["items"]
                if item["split"] == split and (category == "all" or item["category"] == category)]
        pending = [item for item in rows if not item["wav_available"]]
        return {
            "category": category, "split": split,
            "selected": len(rows), "already_imported": len(rows) - len(pending),
            "pending_total": len(pending), "attempt_limit": limit,
            "candidates": pending[:limit],
        }

    def fetch(self, category: str = "Speech", split: str = "balanced_train",
              limit: int = 24, *, confirm_rights: bool = False,
              source_dir: str | Path | None = None,
              youtube_permission: bool = False) -> dict:
        if not confirm_rights:
            raise ValueError("Confirme direitos de uso com --confirm-rights")
        if source_dir is None and not youtube_permission:
            raise ValueError("Acesso online exige --confirm-youtube-permission e autorização real")
        if source_dir is not None and youtube_permission:
            raise ValueError("Escolha apenas uma fonte: --source-dir ou --confirm-youtube-permission")
        ffmpeg_exe = resolve_ffmpeg_exe()
        if source_dir is None and importlib.util.find_spec("yt_dlp") is None:
            raise ValueError("Instale a dependência opcional: python -m pip install yt-dlp")
        source_path = Path(source_dir) if source_dir is not None else None
        if source_path is not None and not source_path.is_dir():
            raise ValueError("Diretório de fontes locais não encontrado")

        plan = self.plan(category, split, limit)
        successes, failures = [], []
        for item in plan["candidates"]:
            try:
                result = self._one(item, source_path, ffmpeg_exe)
                successes.append(result)
            except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                # Não incluir stack traces ou comandos externos em relatórios.
                failures.append({"id": item["id"], "category": item["category"],
                                 "reason": str(exc)[:250]})
        report = {key: value for key, value in plan.items() if key != "candidates"}
        report.update({"mode": "local_authorized" if source_path else "youtube_authorized",
                       "attempted": len(plan["candidates"]), "downloaded": len(successes),
                       "failed": len(failures), "successful": successes, "failures": failures,
                       "message": "Arquivos importados são referências acústicas; não diagnósticos clínicos"})
        return report

    def _one(self, item: dict, source_dir: Path | None, ffmpeg_exe: str) -> dict:
        duration = float(item["end_seconds"] - item["start_seconds"])
        if not 0.25 < duration <= 30.0:
            raise ValueError("Intervalo inválido ou longo demais")
        with tempfile.TemporaryDirectory(prefix="tc4-audioset-") as tmp:
            directory = Path(tmp)
            if source_dir is not None:
                source = self._local_source(source_dir, item["youtube_id"])
                # Extrai exatamente o trecho do vídeo completo autorizado.
                extraction = [ffmpeg_exe, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                              "-ss", str(item["start_seconds"]), "-i", str(source)]
            else:
                base = directory / "source.%(ext)s"
                url = "https://www.youtube.com/watch?v=" + item["youtube_id"]
                command = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-progress",
                           "--ffmpeg-location", ffmpeg_exe,
                           "--download-sections", f"*{item['start_seconds']}-{item['end_seconds']}",
                           "-f", "bestaudio/best", "-o", str(base), url]
                self._run(command, timeout=180, action="Obtenção da mídia")
                sources = [path for path in directory.glob("source.*") if path.is_file()]
                if len(sources) != 1:
                    raise ValueError("Mídia de origem ausente ou ambígua após obtenção")
                source = sources[0]
                extraction = [ffmpeg_exe, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                              "-i", str(source)]

            wav = directory / "clip.wav"
            self._run([*extraction, "-vn", "-t", str(duration), "-ac", "1", "-ar", "16000",
                       "-c:a", "pcm_s16le", str(wav)], timeout=90, action="Conversão WAV")
            if not wav.is_file() or wav.stat().st_size < 44:
                raise ValueError("Arquivo WAV não foi produzido")
            result = self.samples.import_clip(item["id"], wav)
            self._audit(item, result, "local_authorized" if source_dir else "youtube_authorized")
            return {"id": item["id"], "category": item["category"],
                    "split": item["split"], "sha256": result["sha256"]}

    @staticmethod
    def _run(command: list[str], *, timeout: int, action: str) -> None:
        try:
            completed = subprocess.run(command, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, timeout=timeout, check=False)
        except FileNotFoundError as exc:
            raise ValueError(f"Ferramenta ausente durante {action}") from exc
        if completed.returncode != 0:
            raise ValueError(f"{action} falhou (código {completed.returncode}); fonte indisponível, não autorizada ou formato incompatível")

    @staticmethod
    def _local_source(source_dir: Path, youtube_id: str) -> Path:
        supported = (".mp4", ".webm", ".mkv", ".m4a", ".mp3", ".wav", ".ogg")
        candidates = [source_dir / f"{youtube_id}{extension}" for extension in supported]
        matches = [path for path in candidates if path.is_file()]
        if len(matches) != 1:
            raise ValueError("Esperado um arquivo local com nome <youtube_id> e extensão suportada")
        return matches[0]

    def _audit(self, item: dict, result: dict, mode: str) -> None:
        self.samples.workspace.mkdir(parents=True, exist_ok=True)
        entry = {"at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "id": item["id"], "youtube_id": item["youtube_id"],
                 "category": item["category"], "split": item["split"],
                 "start_seconds": item["start_seconds"], "end_seconds": item["end_seconds"],
                 "mode": mode, "wav_sha256": result["sha256"],
                 "source_verified": False, "rights_confirmed_by_user": True}
        with (self.samples.workspace / "authorized_acquisitions.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
