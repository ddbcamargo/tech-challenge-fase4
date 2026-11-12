# 🧪 Plano de testes — v0.9.0

## Terminal (Windows 11, Git Bash)

```bash
cd /c/GITHUB/tech-challenge-fase4
source .venv/Scripts/activate
python -m pip install -e ".[all,test]"
python -m pytest -q
python -m fase4 doctor
python -m fase4 run
```

## Interface — teste obrigatório

1. **📦 Dados:** preparar amostras e importar o PSV da PhysioNet no paciente
   `TC4-P001` (requer internet na primeira vez).
2. **🫀 Monitoramento:** analisar dados de sinais vitais, prescrições e
   movimentação. Confirmar `MOVEMENT_*`, `RX_CHANGE_*` e, se a amostra possuir
   histórico suficiente, `VITAL_*`. Todos têm origem e evidência.
3. **⏯️ Replay:** iniciar, pausar e avançar horas automaticamente (3 s por passo); verificar que não são antecipados registros futuros.
4. **🎙️ Áudio:** gravar/enviar WAV encenado curto com a frase
   “Estou com falta de ar e dor no peito”. Chamar Azure, verificar Speech,
   sentimento/entidades/frases-chave, termos críticos e histórico no SQLite.
   Sem chaves, verificar apenas inspeção local. **Nunca use gravação real.**
5. **🎥 Vídeo:** clicar em preparar MediaPipe (download oficial), enviar vídeo
   consentido de fisioterapia e gerar relatório JSON. Verificar quantos frames
   tiveram pose e quantos tiveram desvios. Um vídeo sem pose deve informar isso.
6. **🚨 Alertas:** verificar alertas de modalidades diferentes, abrir evidências,
   procurar `MULTIMODAL_REVIEW`, marcar uma ocorrência como revisada e verificar
   persistência após reiniciar.

## Resultados e limites

- Testes automatizados de fluxo Azure utilizam **dublês/stubs**, não cobrança de
  chamadas reais. Detecção pose em testes também pode usar dados artificiais.
- Não afirmar acurácia clínica a partir de detecção de outlier ou sentimento.
- Manter o horário de observação original e distinguir do horário de registro
  local no SQLite. A janela de fusão é de registro na **demonstração**.
- Um `.env` local preenchido é necessário para a chamada real de Azure.
- O MediaPipe precisa de vídeo real autorizado e de download do `.task`.
- É permitido rodar testes somente com dados sintéticos para avaliar o código,
  mas esses resultados não substituem evidências com fontes reais adequadas.
