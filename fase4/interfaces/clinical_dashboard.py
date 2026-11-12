"""Interface simplificada de demonstração alinhada ao enunciado FIAP Fase 4.

Concentra operações e visualizações. Todas as regras ficam na aplicação/domínio.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from .dashboard_sections import temporary_upload
from .audio_presentation import audio_view


def monitoring_tab(app, patient_id: str) -> None:
    st.subheader("🫀 Monitoramento preventivo — caso demonstrativo")
    st.caption("PhysioNet: série histórica pública. Prescrições e movimentação: dados simulados. "
               "A atualização é sob demanda, NÃO um sistema hospitalar em tempo real.")
    vitals = app.vitals(patient_id)
    movements = app.movements(patient_id)
    m1, m2, m3 = st.columns(3)
    m1.metric("Medições vitais", len(vitals))
    m2.metric("Pontos de movimentação simulada", len(movements))
    m3.metric("Alertas pendentes", sum(x["status"] == "pending_review" for x in app.alerts(patient_id)))
    if st.button("🔍 Analisar sinais vitais, prescrições e movimentação",
                 type="primary", use_container_width=True, key="run_all_monitoring"):
        with st.spinner("Aplicando regras verificáveis e correlacionando eventos..."):
            result = app.scan_monitoring(patient_id)
        st.success("Verificação concluída. Veja os alertas e evidências na última aba.")
        st.json(result)
    if not vitals:
        st.info("Para analisar sinais vitais reais do conjunto sugerido pela FIAP, "
                "prepare/importe a amostra PhysioNet na aba 📦 Dados.")
    if movements:
        st.markdown("#### 🚶 Trajetória simulada durante internação")
        st.caption("Coordenadas fictícias em metros, sem coleta por câmera ou sensor real.")
        frame = pd.DataFrame(movements)
        st.line_chart(frame.set_index("observed_at")[["x_m", "y_m"]])
        with st.expander("Ver medições simuladas"):
            st.dataframe(frame, use_container_width=True, hide_index=True)
    st.markdown("#### 💊 Alterações de prescrição")
    st.caption("Cenários fictícios. O sistema compara dose, unidade e frequência; "
               "não sugere tratamentos ou condutas clínicas.")
    st.markdown("#### 🔗 Integração de eventos")
    st.info("Ao analisar áudio e vídeo ou gerar alertas de monitoramento para o mesmo caso, "
            "a aplicação associa alertas de modalidades diferentes registrados na janela de 30 minutos. "
            "A associação é demonstrativa, não representa causalidade médica.")



def render_audio_analysis(report: dict) -> None:
    """Exibe resultado da consulta sem JSON bruto ou detalhes de modelos opcionais."""
    view = audio_view(report)
    st.markdown("**Transcrição da consulta**")
    st.write(view["transcript"])
    st.metric("Sentimento do texto", view["sentiment"])
    if view["sentiment_scores"]:
        st.dataframe(pd.DataFrame([
            {"Sentimento": label, "Confiança (%)": confidence}
            for label, confidence in view["sentiment_scores"].items()
        ]), hide_index=True, use_container_width=True)
    st.caption("Sentimento é uma classificação linguística, não uma conclusão clínica.")

    st.markdown("**Expressões-chave extraídas pelo Azure**")
    if view["key_phrases"]:
        st.dataframe(pd.DataFrame({"Expressão identificada": view["key_phrases"]}),
                     hide_index=True, use_container_width=True)
    else:
        st.caption("Nenhuma expressão-chave retornada nesta análise.")

    st.markdown("**Entidades identificadas pelo Azure**")
    if view["entities"]:
        st.dataframe(pd.DataFrame(view["entities"]),
                     hide_index=True, use_container_width=True)
    else:
        st.caption("Nenhuma entidade retornada nesta análise.")

    st.markdown("**Queixas e limitações mencionadas**")
    if view["critical_evidence"]:
        st.warning("Foram encontrados trechos para revisão humana. O destaque usa regras "
                   "de texto explícitas e não representa classificação de gravidade.")
        st.dataframe(pd.DataFrame(view["critical_evidence"]),
                     hide_index=True, use_container_width=True)
    else:
        st.caption("Nenhuma expressão prevista nas regras locais foi identificada.")

    st.markdown("**Indicadores técnicos do áudio**")
    acoustic = [view["duration_seconds"], view["rms_dbfs"],
                view["low_energy_fraction"], view["clipped_fraction"]]
    if all(value is None for value in acoustic):
        st.caption("Indicadores técnicos indisponíveis nesta análise.")
    else:
        a, b, c, d = st.columns(4)
        a.metric("Duração", f"{view['duration_seconds']:.2f} s" if view["duration_seconds"] is not None else "—")
        b.metric("Energia RMS", f"{view['rms_dbfs']:.2f} dBFS" if view["rms_dbfs"] is not None else "—")
        c.metric("Baixa energia", f"{100 * view['low_energy_fraction']:.1f}%" if view["low_energy_fraction"] is not None else "—")
        d.metric("Saturação", f"{100 * view['clipped_fraction']:.2f}%" if view["clipped_fraction"] is not None else "—")
    if view["voice_indicators"]:
        st.dataframe(pd.DataFrame([
            {"Observação": item.get("description", ""), "Valor": item.get("value", "")}
            for item in view["voice_indicators"]
        ]), hide_index=True, use_container_width=True)
    st.caption("Pausas, energia e saturação descrevem o sinal; não diagnosticam alterações vocais.")


def audio_tab(app, patient_id: str) -> None:
    st.subheader("🎙️ Consulta encenada — Azure Speech + Language")
    st.caption("Grave uma fala fictícia ou envie WAV PCM16 mono 16 kHz, até 30 segundos. "
               "Não use dados de pacientes reais ou informações sensíveis.")
    recorded = st.audio_input("🎤 Gravar fala fictícia", sample_rate=16000,
                              key="tc4_clinical_recorded")
    uploaded = st.file_uploader("📁 Ou enviar um WAV", type=["wav"],
                                key="tc4_clinical_upload")
    source = uploaded if uploaded is not None else recorded
    if source is not None:
        st.audio(source)
    configured = all(os.getenv(name, "").strip() for name in (
        "AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION", "AZURE_LANGUAGE_KEY",
        "AZURE_LANGUAGE_ENDPOINT"))
    if not configured:
        st.info("Configure as quatro variáveis Azure no `.env`. "
                "A inspeção local funciona sem chave.")
    local_col, azure_col = st.columns(2)
    with local_col:
        local = st.button("🔎 Inspecionar sinal local", disabled=source is None,
                          use_container_width=True)
    with azure_col:
        azure = st.button("☁️ Transcrever e analisar (Azure)",
                          disabled=source is None or not configured,
                          type="primary", use_container_width=True)
    if local or azure:
        try:
            with temporary_upload(source) as wav:
                if azure:
                    with st.spinner("Speech-to-Text e Text Analytics..."):
                        result = app.process_audio(patient_id, wav, source.name)
                    st.session_state[f"tc4_audio_{patient_id}"] = result
                    st.success("Transcrição, sentimento, termos e evidências armazenados no SQLite.")
                else:
                    st.session_state[f"tc4_local_{patient_id}"] = app.inspect_audio(
                        patient_id, wav, source.name)
        except Exception as error:
            from ..infrastructure.azure import AzureProcessingError, AzureNotConfigured
            if isinstance(error, (ValueError, OSError, AzureProcessingError, AzureNotConfigured)):
                st.error(str(error))
            else:
                st.error("Não foi possível analisar o WAV. Confira formato e configuração do Azure.")
    local_report = st.session_state.get(f"tc4_local_{patient_id}")
    if local_report:
        st.markdown("#### 🔉 Indicadores acústicos descritivos")
        a, b, c = st.columns(3)
        a.metric("Duração", f"{local_report['duration_seconds']} s")
        b.metric("Baixa energia", f"{100 * local_report['low_energy_fraction']:.1f}%")
        c.metric("Saturação", f"{100 * local_report['clipped_fraction']:.2f}%")
        st.caption("Essas medidas não identificam, por si só, disartria, fadiga ou dificuldade respiratória.")
    report = st.session_state.get(f"tc4_audio_{patient_id}")
    if report:
        st.markdown("#### 📝 Análise da consulta")
        render_audio_analysis(report)
        relevant = [row for row in app.alerts(patient_id)
                    if row["modality"] == "audio" and row["status"] == "pending_review"]
        if relevant:
            st.info(f"{len(relevant)} alerta(s) de áudio aguardando revisão neste caso. "
                    "Confira as evidências na aba 🚨 Alertas.")

    st.divider()
    st.markdown("#### 📋 Histórico de consultas deste caso")
    history = [row for row in app.media_events(patient_id, "audio", 30)
               if "azure" in row["result"]]
    if not history:
        st.caption("Nenhuma gravação transcrita ainda.")
    for row in history:
        result = row["result"]
        view = audio_view(result)
        with st.expander(f"{row['occurred_at']} · {row['source_name']} · "
                         f"sentimento: {view['sentiment']}"):
            render_audio_analysis(result)


def video_tab(app, patient_id: str) -> None:
    st.subheader("🎥 Fisioterapia — MediaPipe Pose Landmarker")
    st.caption("Vídeo MP4 curto, encenado/consentido, com corpo visível. "
               "As referências são estatísticas do próprio vídeo, não padrões clínicos.")
    state = app.pose_model_status()
    if not state["ready"]:
        if st.button("📥 Preparar MediaPipe Lite"):
            try:
                state = app.prepare_pose_model()
                st.success("Modelo preparado. Pode analisar um MP4.")
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        else:
            st.info("Prepare o modelo antes da primeira análise.")
    uploaded = st.file_uploader("Enviar MP4 de movimento", type=["mp4"],
                                key="tc4_clinical_video")
    if uploaded:
        st.video(uploaded)
    if st.button("🦵 Analisar e gerar relatório", disabled=uploaded is None or not state["ready"],
                 type="primary", key="tc4_analyze_pose"):
        try:
            with st.spinner("MediaPipe: análise dos quadros e ângulos articulares..."):
                with temporary_upload(uploaded) as path:
                    result = app.process_video(patient_id, path, uploaded.name)
            st.session_state[f"tc4_video_{patient_id}"] = result
        except Exception:
            st.error("Falha ao processar o vídeo. Confira modelo, MP4 e dependências MediaPipe/OpenCV.")
    report = st.session_state.get(f"tc4_video_{patient_id}")
    if report:
        c1, c2, c3 = st.columns(3)
        c1.metric("Quadros amostrados", len(report["samples"]))
        c2.metric("Posturas detectadas", report["pose_detected_frames"])
        c3.metric("Desvios", report["alert_count"])
        if not report["pose_detected_frames"]:
            st.warning("Nenhuma postura encontrada. Use vídeo mais iluminado com corpo inteiro visível.")
        st.dataframe(pd.DataFrame(report["joint_summary"]).T,
                     use_container_width=True)
        if report["samples"]:
            df = pd.DataFrame(report["samples"])
            joint = st.selectbox("Ângulo por quadro", list(report["joint_summary"]),
                                 key="tc4_joint")
            st.line_chart(df.set_index("time_seconds")[[joint]])
        st.download_button("⬇️ Exportar relatório JSON", data=json.dumps(report, ensure_ascii=False,
                           indent=2), file_name="tc4_relatorio_postura.json",
                           mime="application/json")
        st.caption("Relatório automático para revisão. Não detecta falhas cirúrgicas e "
                   "não valida a execução clínica do exercício.")
    history = app.media_events(patient_id, "video", 10)
    if history:
        with st.expander("📋 Relatórios de vídeo anteriores"):
            for item in history:
                st.write(item["occurred_at"], item["source_name"],
                         "desvios:", item["result"].get("alert_count", "?"))


def alerts_tab(app, patient_id: str) -> None:
    st.subheader("🚨 Alertas integrados para revisão da equipe")
    st.caption("Fila simulada de revisão humana. Nada é enviado a prontuários ou serviços hospitalares.")
    if st.button("🔗 Atualizar correlação multimodal"):
        fused = app.correlate_alerts(patient_id)
        st.info("Novo alerta multimodal criado." if fused else
                "Sem novos conjuntos de alertas de modalidades diferentes na janela de 30 minutos.")
    rows = app.alerts(patient_id)
    if not rows:
        st.info("Nenhum alerta. Use o monitoramento, importe PhysioNet, ou analise áudio/vídeo.")
        return
    pending = sum(row["status"] == "pending_review" for row in rows)
    multi = sum(row["modality"] == "multimodal" for row in rows)
    c1, c2 = st.columns(2)
    c1.metric("Aguardando revisão", pending)
    c2.metric("Alertas multimodais", multi)
    dataframe = pd.DataFrame(rows).drop(columns=["evidence_json"], errors="ignore")
    st.dataframe(dataframe, hide_index=True, use_container_width=True)
    selected = st.selectbox("Selecionar evidência de alerta", [row["id"] for row in rows],
                            format_func=lambda alert_id: next(
                                f"#{row['id']} · {row['modality']} · {row['description']}"
                                for row in rows if row["id"] == alert_id))
    row = next(row for row in rows if row["id"] == selected)
    evidence = json.loads(row["evidence_json"])
    if row["modality"] == "audio" and row["code"] == "AUDIO_TERMS":
        st.markdown("**Evidências da consulta de áudio**")
        st.write("Arquivo:", evidence.get("source_name", "Não informado"))
        if evidence.get("media_event_id"):
            st.caption(f"Registro da análise #{evidence['media_event_id']} no SQLite")
        matches = evidence.get("matched_evidence") or []
        if matches:
            st.dataframe(pd.DataFrame([
                {"Trecho do relato": item.get("text", ""),
                 "Categoria": item.get("category", "Trecho de interesse")}
                for item in matches]), hide_index=True, use_container_width=True)
        else:
            st.write(", ".join(evidence.get("terms", [])))
        st.caption("Correspondências textuais que exigem revisão humana; "
                   "não inferem diagnóstico ou prioridade clínica.")
    elif row["modality"] == "multimodal" and evidence.get("source_alert_ids"):
        st.markdown("**Alertas vinculados ao mesmo caso**")
        associated = [item for item in rows
                      if item["id"] in evidence["source_alert_ids"]]
        if associated:
            st.dataframe(pd.DataFrame([
                {"Alerta": item["id"], "Origem": item["modality"],
                 "Descrição": item["description"]} for item in associated
            ]), hide_index=True, use_container_width=True)
        st.caption("Correlação demonstrativa pelo horário de registro, sem inferir causalidade.")
    else:
        st.json(evidence)
    st.caption(f"Ocorrência original: {row['observed_at']} · "
               f"registrada: {row.get('recorded_at', 'legado')} · estado: {row['status']}")
    if row["status"] == "pending_review":
        reviewed, dismissed = st.columns(2)
        with reviewed:
            if st.button("✅ Revisado por responsável", key="tc4_review", use_container_width=True):
                app.review_alert(selected, patient_id, "reviewed")
                st.rerun()
        with dismissed:
            if st.button("➖ Descartar alerta", key="tc4_dismiss", use_container_width=True):
                app.review_alert(selected, patient_id, "dismissed")
                st.rerun()
    st.download_button("⬇️ Exportar alertas JSON", data=json.dumps(rows, ensure_ascii=False,
                       indent=2), file_name=f"tc4_alertas_{patient_id}.json",
                       mime="application/json")
    st.warning("Fusão baseada no horário de registro local da demonstração. "
               "Eventos não devem ser interpretados como simultaneidade ou risco clínico real.")


def replay_tab(app, patient_id: str) -> None:
    """Reprodução automática de série histórica; avança só observações já liberadas."""
    st.subheader("⏯️ Replay progressivo de sinais vitais — PhysioNet")
    st.caption("Um passo histórico a cada três segundos. Isto é reprodução simulada, "
               "não captura por sensores nem monitoramento hospitalar ao vivo.")
    sources = {item["source"]: item for item in app.replay_sources(patient_id)}
    if not sources:
        st.info("Importe uma amostra PhysioNet na aba 📦 Dados para iniciar o replay.")
        return
    selected = st.selectbox("Origem do arquivo PSV", list(sources),
                            key=f"tc4_play_source_{patient_id}")
    pos_key = f"tc4_play_position_{patient_id}_{selected}"
    active_key = f"tc4_play_active_{patient_id}_{selected}"
    if pos_key not in st.session_state:
        st.session_state[pos_key] = 0
    if active_key not in st.session_state:
        st.session_state[active_key] = False
    start, pause, reset = st.columns(3)
    with start:
        if st.button("▶️ Iniciar replay automático", key="tc4_start", use_container_width=True):
            st.session_state[active_key] = True
    with pause:
        if st.button("⏸️ Pausar", key="tc4_pause", use_container_width=True):
            st.session_state[active_key] = False
    with reset:
        if st.button("↩️ Reiniciar visualização", key="tc4_reset", use_container_width=True):
            st.session_state[active_key] = False
            st.session_state[pos_key] = 0
    st.caption("Ao reiniciar a visualização, os alertas persistidos NÃO são apagados.")

    @st.fragment(run_every="3s")
    def render_current_step() -> None:
        current = app.replay_preview(patient_id, selected, st.session_state[pos_key])
        if st.session_state[active_key] and current.position < current.total_steps:
            current = app.replay_next(patient_id, selected, current.position)
            st.session_state[pos_key] = current.position
        if current.position == current.total_steps:
            st.session_state[active_key] = False
        st.progress(current.position / current.total_steps)
        st.write(f"**Hora {current.position} de {current.total_steps}** · "
                 f"{current.observed_at or 'aguardando início'}")
        if current.current_values:
            for column, (key, unit) in zip(st.columns(4),
                                           (("HR", "bpm"), ("O2Sat", "%"),
                                            ("SBP", "mmHg"), ("Resp", "rpm"))):
                value = current.current_values.get(key)
                column.metric(key, f"{value:g} {unit}" if value is not None else "sem leitura")
        if current.new_events:
            st.warning(f"{len(current.new_events)} desvio(s) estatístico(s) neste passo. "
                       "Abra 🚨 Alertas para revisão.")
        if current.history:
            df = pd.DataFrame(current.history)
            option = st.selectbox("Métrica", sorted(df["metric"].unique()),
                                  key=f"tc4_replay_metric_{patient_id}_{selected}")
            st.line_chart(df[df["metric"] == option].set_index("observed_at")["value"])
        if st.button("⏭️ Avançar uma hora", disabled=current.position == current.total_steps,
                     key=f"tc4_next_{patient_id}_{selected}"):
            updated = app.replay_next(patient_id, selected, current.position)
            st.session_state[pos_key] = updated.position
            st.rerun(scope="fragment")

    render_current_step()
