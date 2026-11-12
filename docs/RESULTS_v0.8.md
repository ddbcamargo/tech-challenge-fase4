# 📊 Resultados verificáveis — versão 0.8

## 🧪 Execução local controlada

- Ambiente de testes: Python 3.13, NumPy 2.x, scikit-learn 1.x e pytest.
- **47 testes automáticos aprovados** (`python -m pytest -q` e `python -m unittest discover -s tests -q`).
- **Sem chamadas Azure reais** no ambiente de desenvolvimento; SDKs da nuvem permanecem isolados por testes simulados.
- **Sem validação visual do Streamlit** neste ambiente (Streamlit não instalado); a interface foi compilada e os casos de uso foram testados.
- Não foi usado dado de paciente real no treinamento.

## 🎙️ Demonstração reproduzível

1. Gerados **48 sinais sintéticos de referência** programaticamente.
2. Treinado o `StandardScaler` + `IsolationForest` com `random_state=42`.
3. Gerados dois novos WAVs artificiais e extraídas as dez características acústicas.
4. Um experimento da execução local reportou os resultados abaixo. Ambos são **sinais artificiais, sem voz humana**.

| Amostra | `ml_prediction` | `quality_flags` | `prediction` combinado | Observação |
|---|---|---|---|---|
| `sinal_sintetico_referencia.wav` | `inlier` | Nenhum | `inlier` | Forma de onda próxima à referência |
| `sinal_sintetico_alterado.wav` | `inlier` | `CLIPPING` | `outlier` | Saturação proposital detectada por regra de qualidade independente |

**Importante:** o Isolation Forest **não classificou o sinal alterado como outlier neste ensaio**. O resultado combinado foi `outlier` devido ao aviso objetivo de saturação. Isso demonstra que a saída não esconde limitações do ML nem apresenta o alerta de qualidade como previsão médica.

O caso alterado foi gravado no SQLite como `media_event` e gerou um alerta de severidade `info` com código `VOICE_ACOUSTIC_OUTLIER`, para revisão acadêmica.

## 🩺 O que não foi validado

Nenhuma medida de precisão/recall/sensibilidade clínica é reportada, porque faltam amostras rotuladas confiáveis com sintomas vocais. O treinamento em ondas artificiais não generaliza necessariamente para fala real. Um diagnóstico de fadiga vocal, disartria ou dificuldade respiratória está **fora do escopo validado** desta versão.

## ▶️ Como reproduzir

```bash
python -m fase4 voice-train-demo
python -m fase4 voice-demo-files
python -m fase4 init
python -m fase4 voice-analyze data/demo/voice/sinal_sintetico_referencia.wav --patient TC4-P001
python -m fase4 voice-analyze data/demo/voice/sinal_sintetico_alterado.wav --patient TC4-P001
python -m fase4 alerts --patient TC4-P001
```

Para a validação real de Speech/Language com áudio humano encenado, consulte [TEST_PLAN_v0.8.md](TEST_PLAN_v0.8.md).
