"""Upload temporário e aba de dados oficiais compartilhados pelo painel Streamlit."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

OFFICIAL_ROOT = Path("data/raw/official")
SAMPLE_FILE = OFFICIAL_ROOT / "p100679.psv"


def save_upload(uploaded_file) -> Path:
    content = uploaded_file.getvalue()
    if len(content) > 60 * 1024 * 1024:
        raise ValueError("Arquivo acima de 60 MiB; envie um trecho curto")
    directory = Path("data/uploads")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{uuid4().hex}{Path(uploaded_file.name).suffix.lower()}"
    target.write_bytes(content)
    return target


@contextmanager
def temporary_upload(uploaded_file):
    """Remove apenas a cópia temporária produzida nesta operação."""
    target = save_upload(uploaded_file)
    try:
        yield target
    finally:
        target.unlink(missing_ok=True)


def data_tab(app, patient_id: str, patient_total: int) -> None:
    st.subheader("📦 Preparar a demonstração")
    st.caption("As identidades são fictícias; a amostra PhysioNet permanece uma série pública independente.")
    records = app.vitals(patient_id)
    left, right = st.columns(2)
    left.metric("Pacientes fictícios", patient_total)
    right.metric("Medições neste caso", len(records))

    st.markdown("**Passo 1 — obter os arquivos oficiais**")
    if st.button("📥 Preparar amostras oficiais", key="prepare_official"):
        try:
            with st.spinner("Obtendo amostras pequenas e verificando os arquivos..."):
                report = app.prepare_datasets(OFFICIAL_ROOT)
            if not report["ready"]:
                raise ValueError(report.get("validation_error", "Dados oficiais incompletos"))
            st.session_state["notice"] = "Arquivos PhysioNet e AudioSet preparados e validados."
            st.rerun()
        except (OSError, ValueError) as error:
            st.error(f"Não foi possível preparar os arquivos: {error}")

    st.markdown("**Passo 2 — associar uma série ao caso demonstrativo**")
    st.caption("O vínculo é apenas para replay; não identifica o paciente real da fonte.")
    if not SAMPLE_FILE.is_file():
        st.info("A amostra ainda não foi baixada. Clique em 'Preparar amostras oficiais' acima.")
    if st.button("🫀 Carregar amostra PhysioNet neste caso",
                 disabled=not SAMPLE_FILE.is_file(), key="use_official_sample"):
        try:
            report = app.validate_datasets(OFFICIAL_ROOT)
            if not report["ready"]:
                raise ValueError(report.get("validation_error", "Arquivo sem validação de integridade"))
            count = app.import_physionet(SAMPLE_FILE, patient_id)
            st.session_state["notice"] = f"{count} novas medições adicionadas. Vá à aba Replay temporal."
            st.rerun()
        except (OSError, ValueError) as error:
            st.error(f"Importação interrompida: {error}")

    with st.expander("Ou importar outro arquivo PSV oficial"):
        uploaded = st.file_uploader("Arquivo PhysioNet .psv", type=["psv"], key="psv_upload")
        if st.button("Importar PSV selecionado", disabled=uploaded is None, key="import_psv"):
            try:
                with temporary_upload(uploaded) as path:
                    count = app.import_physionet(path, patient_id)
                st.session_state["notice"] = f"{count} novas medições importadas do arquivo selecionado."
                st.rerun()
            except (OSError, ValueError) as error:
                st.error(str(error))

    if records:
        st.markdown("**Medições disponíveis**")
        st.dataframe(pd.DataFrame(records).tail(20), hide_index=True, use_container_width=True)
    else:
        st.info("Nenhuma medição neste caso ainda. Execute os passos 1 e 2 para preencher o painel.")
