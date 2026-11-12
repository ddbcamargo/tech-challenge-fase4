# ✅ Roteiro de testes — Tech Challenge Fase 4, v0.8

## 🔧 Preparação

- [ ] Preserve seu `.env`, `.venv`, `data/` e `models/` ao atualizar o ZIP.
- [ ] `source .venv/Scripts/activate` no Git Bash.
- [ ] `python -m pip install -e ".[all,test]"`.
- [ ] `python -m pytest -q` ou `python -m unittest discover -s tests -v`.
- [ ] `python -m fase4 doctor` sem exibir chaves; procure `azure_*_configured` e `voice_model`.
- [ ] `python -m fase4 run` abre o dashboard sem fazer chamadas automáticas ao Azure.

## 📦 1. Sinais vitais (oficiais)

- [ ] Aba **Dados**: preparar arquivos oficiais PhysioNet/AudioSet e importar um PSV para `TC4-P001`.
- [ ] Aba **Replay**: avançar registros horários e observar sinais vitais.
- [ ] Aba **Alertas**: inspecionar e revisar ocorrências; reproduzir novamente não deve duplicar eventos idênticos.

## 🧠 2. Detecção acústica local (não consome Azure)

- [ ] Aba **Áudio**: treinar baseline de demonstração e gerar dois WAVs artificiais.
- [ ] Baixar e anexar `sinal_sintetico_referencia.wav` e executar **Analisar WAV com modelo local**.
- [ ] Ver `inlier` no resultado combinado do WAV de referência.
- [ ] Repetir para `sinal_sintetico_alterado.wav`: ver `outlier` e aviso `CLIPPING`; o `ml_prediction` pode permanecer `inlier` e deve aparecer **separadamente**.
- [ ] Confirmar entrada no histórico e eventual alerta **informativo** na aba Alertas.
- [ ] Reiniciar Streamlit e confirmar que o histórico persiste.
- [ ] **Não enviar** os dois WAVs sintéticos ao Azure Speech: não contêm fala.

## ☁️ 3. Speech + Language com gravação encenada

- [ ] `.env` privado com `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION=brazilsouth`, `AZURE_LANGUAGE_KEY` e `AZURE_LANGUAGE_ENDPOINT=https://language-tc4.cognitiveservices.azure.com/`.
- [ ] Fazer gravação de uma frase única (10–20 s), sem dados pessoais, salvar WAV **PCM16 mono 16 kHz**. Converter com FFmpeg se necessário: `ffmpeg -i consulta.m4a -ac 1 -ar 16000 -c:a pcm_s16le consulta.wav`.
- [ ] Inspecionar localmente, depois clicar **Transcrever e analisar com Azure** **uma vez**.
- [ ] Verificar transcrição, sentimento, expressões-chave e entidades (listas vazias são possíveis).
- [ ] Confirmar campo do detector vocal no **histórico Azure** (se modelo estiver treinado).
- [ ] Reiniciar a interface e verificar que o registro persiste.
- [ ] Não compartilhar chaves, transcrições reais nem logs brutos do Azure.

## 🎥 4. Vídeo MediaPipe

- [ ] Aba **Vídeo**: preparar modelo MediaPipe Lite, se necessário.
- [ ] Enviar MP4 curto (fisioterapia encenada, autorizado), inspecionar e analisar.
- [ ] Confirmar frames com postura e gráfico de ângulos, sem inferir diagnóstico.

## 🚨 5. Alertas e evidências

- [ ] Verificar alertas de sinais vitais, prescrições e áudios, quando existirem.
- [ ] Marcar uma ocorrência `pending_review` como `reviewed` ou `dismissed`.
- [ ] Confirmar que o resultado permanece no banco após reabrir Streamlit.

## 📊 Evidências para entrega

Registrar capturas **sem credenciais** da interface: replay com sinal vital, resultado de vídeo, resultado de fala transcrita, score do detector vocal e fila de revisão. **Anotar separadamente** quais componentes foram testados com dados públicos, dados sintéticos, SDKs simulados e Azure real.

**Ainda não concluído na v0.8:** detecção clínica validada de disartria/fadiga, fluxo contínuo de áudio de consulta, fusão multimodal completa e notificação real à equipe. São objetivos posteriores do desafio.
