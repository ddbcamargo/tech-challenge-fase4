"""Preparação de áudio em um fluxo: índices oficiais -> clips permitidos -> treino.

A ausência de mídia autorizada produz somente um baseline DEMO claramente rotulado.
A preparação não confunde índices AudioSet ou sinais sintéticos com WAVs oficiais.
"""
from __future__ import annotations

from pathlib import Path

from ..infrastructure.datasets.audioset_fetch import AuthorizedAudioSetFetcher
from ..infrastructure.datasets.audioset_stratified import (
    EVAL_QUOTAS, MIN_REFERENCE, TRAIN_QUOTAS, TRAINABLE_CATEGORIES,
)


def ensure_voice_ready(application) -> dict:
    """Garante modelo carregável e WAVs de exemplo sem rede nem downloads.

    Pode promover um modelo sintético a uma referência AudioSet apenas quando
    houver amostras oficiais WAV de treinamento suficientes já importadas.
    """
    current = application.voice_model_status()
    try:
        selection = application.audioset_stratified_status()
        speech_count = next((row["available"] for row in selection.get("by_category", [])
                            if row["split"] == "balanced_train" and row["category"] == "Speech"), 0)
        if speech_count >= MIN_REFERENCE and (not current["ready"] or
                                                current.get("mode") == "synthetic_demo"):
            current = application.audioset_train_category("Speech")
    except (OSError, ValueError, KeyError):
        # O modo demonstrativo continua disponível sem rede, inclusive quando
        # ainda não existem os CSVs oficiais ou a seleção precisa de reparo.
        pass
    if not current["ready"]:
        current = application.train_voice_demo()
    examples = application.prepare_voice_demo()
    return {"model": current, "examples": examples,
            "real_audioset_trained": current.get("mode", "").startswith("audioset_")}


def setup_audio(application, *, official_download: bool = True,
                source_dir: str | Path | None = None, online_permission: bool = False,
                confirm_rights: bool = False, category: str = "Speech",
                limit: int = 60, seed: int = 42) -> dict:
    """Automatiza as etapas disponíveis; nunca declara fonte real sem WAV.

    -- Sem autorização: baixa apenas CSVs oficiais e treina demonstração.
    -- Fonte autorizada: tenta até `limit` segmentos e treina o modelo real.
    -- Avaliação `eval` nunca é usada no treinamento.
    """
    if category not in (*TRAINABLE_CATEGORIES, "all"):
        raise ValueError("Categoria inválida")
    if not 1 <= limit <= 100:
        raise ValueError("Use --limit entre 1 e 100")
    if (source_dir is not None or online_permission) and not confirm_rights:
        raise ValueError("Fontes de mídia exigem confirmação de direitos")
    if online_permission and source_dir is not None:
        raise ValueError("Escolha somente fonte local OU online")

    report: dict = {"dataset": "Google AudioSet v1", "category": category,
                    "steps": [], "warnings": [], "fetched": [], "training": []}
    if official_download:
        try:
            official = application.prepare_datasets("data/raw/official")
            report["steps"].append({"name": "official_indices", "ready": official.get("ready", False)})
        except (OSError, ValueError) as exc:
            report["warnings"].append(f"Não foi possível preparar CSVs oficiais: {exc}")

    try:
        selection = application.audioset_stratified_status()
        if not selection.get("ready"):
            # Aumenta a seleção Speech, conserva as cotas independentes das demais classes.
            quotas = {**TRAIN_QUOTAS, "Speech": 60}
            selection = application.audioset_stratified_select(seed, quotas, EVAL_QUOTAS)
        report["steps"].append({"name": "stratified_curation", "selected": selection["selected"],
                                "available_wavs": selection["available"]})
    except (OSError, ValueError, KeyError) as exc:
        report["warnings"].append(f"Curadoria indisponível: {exc}")
        selection = {"ready": False}

    if (source_dir is not None or online_permission) and selection.get("ready"):
        fetcher = AuthorizedAudioSetFetcher(application.stratified_samples)
        categories = TRAINABLE_CATEGORIES if category == "all" else (category,)
        for label in categories:
            try:
                result = fetcher.fetch(label, "balanced_train", limit,
                                       source_dir=source_dir,
                                       youtube_permission=online_permission,
                                       confirm_rights=confirm_rights)
                report["fetched"].append({"category": label,
                                          "attempted": result["attempted"],
                                          "downloaded": result["downloaded"],
                                          "failed": result["failed"]})
            except (OSError, ValueError) as exc:
                report["warnings"].append(f"{label}: mídias não obtidas: {exc}")

    if selection.get("ready"):
        try:
            current = application.audioset_stratified_status()
            for label in (TRAINABLE_CATEGORIES if category == "all" else (category,)):
                available = next((row["available"] for row in current.get("by_category", [])
                                  if row["category"] == label and row["split"] == "balanced_train"), 0)
                if available >= MIN_REFERENCE:
                    # Não refaça um treino válido toda vez que o usuário abre a UI.
                    # Refaça apenas se a seleção ou a quantidade de WAVs mudou.
                    if label == "Speech":
                        previous_model = application.voice_model_status()
                    else:
                        from ..infrastructure.voice_model import IsolationForestVoiceModel
                        previous_model = IsolationForestVoiceModel(
                            f"models/audioset_{label.lower()}.joblib").status()
                    from ..infrastructure.datasets.catalog import file_sha256
                    selection_path = getattr(application.stratified_samples, "selection_path", None)
                    hash_selection = file_sha256(selection_path) if (
                        selection_path is not None and Path(selection_path).is_file()) else None
                    origin = previous_model.get("provenance") or {}
                    if (previous_model.get("ready") and origin.get("label") == label and
                            origin.get("selection_sha256") == hash_selection and
                            previous_model.get("reference_count") == available):
                        trained = previous_model
                        reused = True
                    else:
                        trained = application.audioset_train_category(label)
                        reused = False
                    report["training"].append({"category": label, "mode": trained["mode"],
                                               "reference_count": trained["reference_count"],
                                               "reused": reused})
                else:
                    report["warnings"].append(f"{label}: {available}/{MIN_REFERENCE} WAVs reais; treino oficial pendente")
        except (OSError, ValueError) as exc:
            report["warnings"].append(f"Treino oficial pendente: {exc}")
    ready = ensure_voice_ready(application)
    report["model"] = ready["model"]
    report["examples"] = ready["examples"]
    report["real_audioset_trained"] = ready["real_audioset_trained"]
    if not ready["real_audioset_trained"]:
        report["warnings"].append("Modelo disponível é DEMO sintético, NÃO treinado com áudios reais AudioSet")
    return report
