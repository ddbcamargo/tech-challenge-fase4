"""Configuração local: lê somente o .env da raiz, sem expor credenciais."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_project_environment(env_file: str | Path | None = None) -> bool:
    """Carrega .env local sem sobrescrever variáveis já definidas pelo sistema.

    O caminho explícito evita ler acidentalmente um .env de outra pasta quando
    a aplicação é iniciada pelo Git Bash, Streamlit ou Uvicorn.
    """
    path = Path(env_file) if env_file is not None else PROJECT_ROOT / ".env"
    if not path.is_file():
        return False
    return load_dotenv(dotenv_path=path, override=False, interpolate=False)
