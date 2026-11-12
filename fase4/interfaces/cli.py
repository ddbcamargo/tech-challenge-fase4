"""Entrada principal: um comando para cada operação, sempre via aplicação."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from ..config import load_project_environment
from ..container import build_application


def _dependency(name: str) -> str:
    return "instalado" if importlib.util.find_spec(name) else "ausente"


def _runtime_import_status(name: str) -> str:
    """Confirma que o módulo pode ser carregado, inclusive extensões nativas.

    find_spec() sozinho não identifica um pyarrow instalado mas com DLL ausente
    no Windows. Não expõe valores de ambiente nem realiza requisições externas.
    """
    if importlib.util.find_spec(name) is None:
        return "ausente"
    try:
        importlib.import_module(name)
    except Exception as error:
        return f"falha ao importar ({type(error).__name__}): {str(error)[:180]}"
    return "ok"


def doctor() -> dict:
    """Diagnóstico sem efeitos colaterais e sem exibir credenciais."""
    load_project_environment()
    return {
        "python": sys.version.split()[0],
        "streamlit": _dependency("streamlit"),
        "pyarrow_runtime": _runtime_import_status("pyarrow"),
        "altair_runtime": _runtime_import_status("altair"),
        "fastapi": _dependency("fastapi"),
        "mediapipe": _dependency("mediapipe"),
        "azure_speech": _dependency("azure"),
        "azure_speech_configured": bool(os.getenv("AZURE_SPEECH_KEY") and os.getenv("AZURE_SPEECH_REGION")),
        "azure_language_configured": bool(os.getenv("AZURE_LANGUAGE_KEY") and os.getenv("AZURE_LANGUAGE_ENDPOINT")),
        "pose_model_configured": Path(os.getenv("POSE_MODEL_PATH") or "models/pose_landmarker_lite.task").is_file(),
        "pose_model_path": os.getenv("POSE_MODEL_PATH") or "models/pose_landmarker_lite.task",
        "voice_model_ready": bool(build_application().voice_model_status().get("ready")),
        "local_wav_inspection": "WAV PCM16 mono/estéreo, sem Azure",
        "physionet": "importação PSV disponível; baixe amostras oficiais separadamente",
        "audioset": "índices oficiais + curadoria; obtenção de mídias somente com autorização explícita",
        "audioset_clips": {
            key: value for key, value in build_application().audioset_selection_status().items()
            if key != "items"
        },
        "audioset_stratified": {
            key: value for key, value in build_application().audioset_stratified_status().items()
            if key != "items"
        },
    }


def _launch(module: str, args: list[str], db_path: str) -> int:
    if importlib.util.find_spec(module) is None:
        print(f"Dependência {module} ausente. Instale pip install -e '.[all,test]'", file=sys.stderr)
        return 2
    environment = os.environ.copy()
    environment["FASE4_DB_PATH"] = db_path
    return subprocess.call([sys.executable, "-m", module, *args], env=environment)


def main(argv: list[str] | None = None) -> int:
    load_project_environment()
    parser = argparse.ArgumentParser(
        prog="python -m fase4",
        description="Fase 4: fluxo único para preparar, executar e inspecionar o protótipo",
    )
    parser.add_argument("--db", default=os.getenv("FASE4_DB_PATH", "data/fase4.sqlite3"))
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("doctor", help="Verifica dependências e integrações sem usar credenciais")
    actions.add_parser("init", help="Cria banco do zero e 25 pacientes fictícios")
    actions.add_parser("run", help="Abre Streamlit; treinamento de ML é opcional")
    setup = actions.add_parser("setup-audio", help="CSV -> curadoria -> mídias autorizadas -> treino -> WAVs de exemplo")
    setup.add_argument("--category", choices=["Speech", "Breathing", "Cough", "Wheeze", "all"], default="Speech")
    setup.add_argument("--limit", type=int, default=60)
    setup.add_argument("--source-dir", type=Path, help="Origem local de mídias autorizadas, nomes <youtube_id>.*")
    setup.add_argument("--online-authorized", action="store_true", help="Permite obtenção online SOMENTE com autorização explícita YouTube/titulares")
    setup.add_argument("--confirm-rights", action="store_true", help="Confirma possuir permissão para usar e obter as mídias")
    actions.add_parser("api", help="Inicializa e abre API FastAPI")
    actions.add_parser("patients", help="Lista pacientes fictícios")
    imp = actions.add_parser("import-physionet", help="Importa arquivo PSV público do Challenge 2019")
    imp.add_argument("path", type=Path)
    imp.add_argument("--patient", default="TC4-P001")
    idx = actions.add_parser("audioset-preview", help="Inspeciona o índice oficial do AudioSet")
    idx.add_argument("path", type=Path)
    idx.add_argument("--limit", type=int, default=5)
    prep = actions.add_parser("prepare-datasets", help="Baixa um PSV e três CSVs oficiais com hashes")
    prep.add_argument("--dir", type=Path, default=Path("data/raw/official"))
    valid = actions.add_parser("validate-datasets", help="Valida arquivos oficiais e manifesto sem rede")
    valid.add_argument("--dir", type=Path, default=Path("data/raw/official"))
    actions.add_parser("prepare-pose-model", help="Baixa modelo MediaPipe Lite oficial, se ausente")
    wav = actions.add_parser("inspect-wav", help="Mede energia/pausas acústicas sem Azure")
    wav.add_argument("path", type=Path)
    wav.add_argument("--patient", default="TC4-P001")
    azure_audio = actions.add_parser(
        "analyze-audio", help="Transcreve um WAV fictício com Speech + Language e salva no SQLite"
    )
    azure_audio.add_argument("path", type=Path)
    azure_audio.add_argument("--patient", default="TC4-P001")
    selection = actions.add_parser("audioset-select", help="Seleciona trechos oficiais, sem baixar vídeos")
    selection.add_argument("--label", default="Speech")
    selection.add_argument("--split", choices=["balanced_train", "eval"], default="balanced_train")
    selection.add_argument("--limit", type=int, default=24)
    actions.add_parser("audioset-status", help="Conta trechos da seleção legada e WAVs fornecidos")
    curate = actions.add_parser("audioset-curate", help="Seleciona cinco categorias, treino/avaliação sem vazamento")
    curate.add_argument("--seed", type=int, default=42)
    curate.add_argument("--train-quota", action="append", default=[], metavar="CATEGORY=N",
                        help="Sobrescreve cota de treino, ex. --train-quota Speech=60")
    curate.add_argument("--eval-quota", action="append", default=[], metavar="CATEGORY=N")
    actions.add_parser("audioset-curated-status", help="Exibe contagens e IDs da seleção estratificada")
    fetched = actions.add_parser("audioset-fetch-authorized", help="Obtém lotes de mídias autorizadas e extrai WAVs")
    fetched.add_argument("--category", choices=["Speech", "Breathing", "Cough", "Wheeze", "Silence", "all"], default="Speech")
    fetched.add_argument("--split", choices=["balanced_train", "eval"], default="balanced_train")
    fetched.add_argument("--limit", type=int, default=24, help="No máximo 100 por execução")
    fetched.add_argument("--download", action="store_true", help="Executa; sem essa opção mostra prévia sem rede")
    fetched.add_argument("--confirm-rights", action="store_true", help="Declara que tem direitos de uso da mídia")
    fetched.add_argument("--confirm-youtube-permission", action="store_true",
                         help="Declara autorização aplicável para baixar usando a plataforma YouTube")
    fetched.add_argument("--source-dir", type=Path, help="Diretório de vídeos locais autorizados, nomes <youtube_id>.*")
    fetched.add_argument("--train-after", action="store_true", help="Treina após baixar 12+ itens da classe")
    curated_import = actions.add_parser("audioset-curated-import", help="Importa WAV autorizado para a curadoria")
    curated_import.add_argument("id", type=str)
    curated_import.add_argument("path", type=Path)
    curated_import.add_argument("--confirm-rights", action="store_true", required=False)
    category_train = actions.add_parser("audioset-train-category", help="Treina referência separada por categoria")
    category_train.add_argument("category", choices=["Speech", "Breathing", "Cough", "Wheeze"])
    category_eval = actions.add_parser("audioset-evaluate-category", help="Taxa de desvio no split eval, não acurácia")
    category_eval.add_argument("category", choices=["Speech", "Breathing", "Cough", "Wheeze"])
    audioset_import = actions.add_parser("audioset-import-clip", help="Importa um WAV autorizado de trecho AudioSet")
    audioset_import.add_argument("id", type=str, help="ID mostrado em audioset-status")
    audioset_import.add_argument("path", type=Path, help="WAV PCM16 mono 16kHz, trecho correto")
    actions.add_parser("voice-train-audioset", help="Treina Isolation Forest com >=12 WAVs AudioSet / Speech")
    actions.add_parser("voice-train-demo", help="Treina uma referência sintética, apenas demonstrativa")
    references = actions.add_parser("voice-train-references", help="Treina com >=12 WAVs autorizados e independentes")
    references.add_argument("directory", type=Path)
    actions.add_parser("voice-demo-files", help="Gera dois sinais artificiais para testar o detector, não Azure")
    voice = actions.add_parser("voice-analyze", help="Analisa um WAV localmente, sem Azure")
    voice.add_argument("path", type=Path)
    voice.add_argument("--patient", default="TC4-P001")
    video = actions.add_parser("inspect-video", help="Lê duração e resolução de vídeo com OpenCV")
    video.add_argument("path", type=Path)
    scan = actions.add_parser("scan", help="Calcula alertas para um paciente")
    scan.add_argument("kind", choices=["vitals", "prescriptions", "movement", "all"])
    scan.add_argument("--patient", default="TC4-P001")
    alerts = actions.add_parser("alerts", help="Exibe alertas existentes")
    alerts.add_argument("--patient")
    args = parser.parse_args(argv)

    if args.action == "doctor":
        print(json.dumps(doctor(), ensure_ascii=False, indent=2))
        return 0
    application = build_application(args.db)
    if args.action in {"init", "run", "api"}:
        count = application.bootstrap()
        print(f"Banco preparado: {count} novos pacientes fictícios (até 25 no total)")
        if args.action == "run":
            path = Path(__file__).with_name("dashboard.py")
            return _launch("streamlit", ["run", str(path)], args.db)
        if args.action == "api":
            return _launch("uvicorn", ["fase4.interfaces.api:app", "--reload"], args.db)
        return 0

    try:
        if args.action == "setup-audio":
            from ..interfaces.audio_setup import setup_audio
            result = setup_audio(application, source_dir=args.source_dir,
                                 online_permission=args.online_authorized,
                                 confirm_rights=args.confirm_rights,
                                 category=args.category, limit=args.limit)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.action == "patients":
            print(json.dumps(application.patients(), ensure_ascii=False, indent=2))
        elif args.action == "import-physionet":
            count = application.import_physionet(args.path, args.patient)
            print(f"{count} novas medidas importadas")
        elif args.action == "audioset-preview":
            print(json.dumps(application.audioset_preview(args.path, args.limit),
                             ensure_ascii=False, indent=2))
        elif args.action in {"prepare-datasets", "validate-datasets"}:
            report = (application.prepare_datasets(args.dir) if args.action == "prepare-datasets"
                      else application.validate_datasets(args.dir))
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["ready"] else 1
        elif args.action == "prepare-pose-model":
            print(json.dumps(application.prepare_pose_model(), ensure_ascii=False, indent=2))
        elif args.action == "inspect-wav":
            application.bootstrap()
            print(json.dumps(application.inspect_audio(args.patient, args.path, args.path.name),
                             ensure_ascii=False, indent=2))
        elif args.action == "analyze-audio":
            from ..infrastructure.azure import AzureNotConfigured, AzureProcessingError
            application.bootstrap()
            try:
                report = application.process_audio(args.patient, args.path, args.path.name)
                # Não imprime texto de pacientes no terminal, mesmo em teste fictício.
                print(json.dumps({
                    "saved": True, "patient_id": args.patient,
                    "source_name": args.path.name,
                    "sentiment": report["azure"]["sentiment"],
                    "key_phrase_count": len(report["azure"].get("key_phrases", [])),
                    "entity_count": len(report["azure"].get("entities", [])),
                    "critical_terms": report["critical_terms"],
                }, ensure_ascii=False, indent=2))
            except (AzureNotConfigured, AzureProcessingError) as error:
                parser.error(str(error))
        elif args.action == "audioset-select":
            report = application.audioset_select(args.label, args.split, args.limit)
            print(json.dumps({key: value for key, value in report.items() if key != "items"},
                             ensure_ascii=False, indent=2))
        elif args.action == "audioset-status":
            print(json.dumps(application.audioset_selection_status(), ensure_ascii=False, indent=2))
        elif args.action == "audioset-curate":
            from ..infrastructure.datasets.audioset_stratified import TRAIN_QUOTAS, EVAL_QUOTAS
            def apply_quotas(defaults: dict, overrides: list[str]) -> dict:
                result = dict(defaults)
                for override in overrides:
                    category, sep, raw = override.partition("=")
                    if not sep or category not in result or not raw.isdecimal():
                        raise ValueError(f"Cota inválida: {override}; formato CATEGORY=N")
                    result[category] = int(raw)
                return result
            train_quotas = apply_quotas(TRAIN_QUOTAS, args.train_quota)
            eval_quotas = apply_quotas(EVAL_QUOTAS, args.eval_quota)
            report = application.audioset_stratified_select(args.seed, train_quotas, eval_quotas)
            print(json.dumps({k: v for k, v in report.items() if k != "items"},
                             ensure_ascii=False, indent=2))
        elif args.action == "audioset-curated-status":
            print(json.dumps(application.audioset_stratified_status(), ensure_ascii=False, indent=2))
        elif args.action == "audioset-fetch-authorized":
            from ..infrastructure.datasets.audioset_fetch import AuthorizedAudioSetFetcher
            fetcher = AuthorizedAudioSetFetcher(application.stratified_samples)
            if not args.download:
                planned = fetcher.plan(args.category, args.split, args.limit)
                print(json.dumps({**{k: v for k, v in planned.items() if k != "candidates"},
                                  "ids": [row["id"] for row in planned["candidates"]],
                                  "dry_run": True}, ensure_ascii=False, indent=2))
            else:
                if args.train_after and (args.split != "balanced_train" or args.category in {"all", "Silence"}):
                    raise ValueError("Treinamento posterior exige categoria treinável no split balanced_train")
                report = fetcher.fetch(args.category, args.split, args.limit,
                                       confirm_rights=args.confirm_rights,
                                       youtube_permission=args.confirm_youtube_permission,
                                       source_dir=args.source_dir)
                if args.train_after:
                    try:
                        report["model"] = application.audioset_train_category(args.category)
                    except ValueError as error:
                        report["training_pending"] = str(error)
                print(json.dumps(report, ensure_ascii=False, indent=2))
        elif args.action == "audioset-curated-import":
            if not args.confirm_rights:
                parser.error("Confirme a origem/correspondência e os direitos com --confirm-rights")
            print(json.dumps(application.audioset_stratified_import(args.id, args.path),
                             ensure_ascii=False, indent=2))
        elif args.action == "audioset-train-category":
            print(json.dumps(application.audioset_train_category(args.category),
                             ensure_ascii=False, indent=2))
        elif args.action == "audioset-evaluate-category":
            print(json.dumps(application.audioset_evaluate_category(args.category),
                             ensure_ascii=False, indent=2))
        elif args.action == "audioset-import-clip":
            print(json.dumps(application.audioset_import_clip(args.id, args.path),
                             ensure_ascii=False, indent=2))
        elif args.action == "voice-train-audioset":
            print(json.dumps(application.train_voice_audioset(), ensure_ascii=False, indent=2))
        elif args.action == "voice-train-demo":
            print(json.dumps(application.train_voice_demo(), ensure_ascii=False, indent=2))
        elif args.action == "voice-train-references":
            print(json.dumps(application.train_voice_references(args.directory), ensure_ascii=False, indent=2))
        elif args.action == "voice-demo-files":
            print(json.dumps(application.prepare_voice_demo(), ensure_ascii=False, indent=2))
        elif args.action == "voice-analyze":
            application.bootstrap()
            report = application.analyze_voice(args.patient, args.path, args.path.name)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        elif args.action == "inspect-video":
            print(json.dumps(application.inspect_video(args.path), ensure_ascii=False, indent=2))
        elif args.action == "scan":
            count = 0
            if args.kind in {"vitals", "all"}:
                count += len(application.scan_vitals(args.patient))
            if args.kind in {"prescriptions", "all"}:
                count += len(application.scan_prescriptions(args.patient))
            if args.kind in {"movement", "all"}:
                count += len(application.scan_movements(args.patient))
            application.correlate_alerts(args.patient)
            print(f"{count} eventos identificados (duplicatas ignoradas na persistência)")
        elif args.action == "alerts":
            print(json.dumps(application.alerts(args.patient), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0

