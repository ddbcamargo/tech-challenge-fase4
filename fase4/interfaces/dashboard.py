"""Entrada principal Streamlit para os requisitos obrigatórios da Fase 4."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from fase4.container import build_application
from fase4.interfaces.dashboard_sections import data_tab
from fase4.interfaces.clinical_dashboard import (alerts_tab, audio_tab,
                                                 monitoring_tab, video_tab, replay_tab)


def main() -> None:
    st.set_page_config(page_title="Tech Challenge Fase 4", page_icon="🩺", layout="wide")
    app = build_application()
    app.bootstrap()
    st.title("🩺 Monitoramento multimodal — Tech Challenge 4")
    st.caption("PhysioNet + Google AudioSet (metadados) · Azure Speech + Language · "
               "MediaPipe · regras transparentes de anomalia · revisão humana")
    st.warning("Protótipo acadêmico. Dados públicos e sintéticos, sem diagnóstico ou uso clínico. "
               "Monitoramento e correlação são simulações, não telemetria em tempo real.")
    patients = app.patients()
    patient_id = st.sidebar.selectbox("Caso fictício", [row["patient_id"] for row in patients])
    patient = next(row for row in patients if row["patient_id"] == patient_id)
    st.sidebar.caption(f"{patient['name']} · {patient['ward']}")
    st.sidebar.markdown("""**Demonstração em 5 passos**

1. Preparar/associar a série PhysioNet.
2. Executar monitoramento e replay.
3. Gravar fala fictícia e chamar Azure.
4. Analisar MP4 com MediaPipe.
5. Revisar o alerta multimodal.

""")
    monitoring, data, replay, audio, video, alerts = st.tabs([
        "🫀 Monitoramento", "📦 Dados", "⏯️ Replay", "🎙️ Áudio + Azure",
        "🎥 Vídeo", "🚨 Alertas",
    ])
    with monitoring:
        monitoring_tab(app, patient_id)
    with data:
        data_tab(app, patient_id, len(patients))
    with replay:
        replay_tab(app, patient_id)
    with audio:
        audio_tab(app, patient_id)
    with video:
        video_tab(app, patient_id)
    with alerts:
        alerts_tab(app, patient_id)


if __name__ == "__main__":
    main()
