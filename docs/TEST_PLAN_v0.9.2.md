# 🧪 Roteiro de validação — versão 0.9.2

## 🎯 Objetivo

Comprovar que a interface principal mostra a análise Azure de maneira legível,
identifica **trechos literais do relato** e vincula alertas ao paciente fictício e à
análise de áudio original. Não incluir conteúdo sensível real em áudio de testes.

## 🪟 Preparação no Git Bash

```bash
cd /c/GITHUB/tech-challenge-fase4
source .venv/Scripts/activate
python -m pip install -e ".[all,test]"
python -m pip check
python -c "import pyarrow as pa; import altair; import streamlit; print('PyArrow OK:', pa.__version__)"
python -m pytest -q
python -m fase4 doctor
python -m fase4 run
```

O `.env` deve conter `AZURE_SPEECH_REGION=brazilsouth` (**sem URL**) e as chaves
locais válidas. Não envie o `.env` nem gravações privadas ao GitHub.

## ✅ Cenários para conferência visual

1. Na barra lateral escolha `TC4-P001` e abra **🎙️ Áudio + Azure**.
2. Envie seu WAV encenado de até 30 segundos em PCM16 mono 16 kHz e clique
   **☁️ Transcrever e analisar (Azure)**.
3. Verifique os blocos: **transcrição**, **sentimento Misto**, **expressões-chave**,
   **entidades**, **queixas e limitações mencionadas** e **indicadores técnicos**.
4. No exemplo de dores nas mãos e punhos, confira dois trechos destacados:
   `dores nas mãos e nos punhos` e `têm me impedido de fazer tarefas simples`.
   Esses trechos são regras locais, não diagnósticos retornados pelo Azure.
5. Abra **🚨 Alertas** e procure o alerta de áudio para `TC4-P001`. Selecione
   o alerta e confira categoria, trecho e ID de origem de áudio no SQLite.
6. Execute **🫀 Monitoramento** para o mesmo paciente e volte a **🚨 Alertas**;
   confira a correlação de fontes diferentes. Não supor simultaneidade clínica.
7. Reinicie o Streamlit, abra **📋 Histórico de consultas deste caso** e verifique
   que todos os resultados estão disponíveis **sem nova chamada Azure**.
8. Selecione `TC4-P002`: seus dados não devem incluir eventos de `TC4-P001`.
9. Verifique que a interface não apresenta texto de estado de modelo ou detalhes
   internos de treinamento acústico.

## 🧰 Testes automatizados

- `tests/test_audio_presentation_v092.py`: identificação literal, negações,
  apresentação sem objetos internos, histórico compatível e vínculo de alertas.
- **91 testes aprovados** após inclusão de três regressões do diagnóstico PyArrow, no ambiente de revisão (Linux), sem chaves Azure,
  sem consumir cota F0 e sem MediaPipe real.
- Foi realizado um teste local de processamento do arquivo `0001_azure_16khz.wav`
  com adaptadores Azure simulados: duração de 8,94 s, dois trechos identificados,
  registro de alerta de áudio e alerta multimodal vinculados a `TC4-P001`.
  Esse teste **não** é uma nova chamada Azure real.
- A etapa visual no **Windows 11** deve ser confirmada pelo usuário, pois não é
  executada na suíte de testes do pacote.

## ⚠️ Limitações

As métricas de energia e pausas descrevem o sinal acústico; sentimentos e entidades
são estimativas de um serviço de linguagem e podem conter erros semânticos.
A fila de alertas é demonstrativa e exige revisão humana. Não faz diagnóstico.

## 🪟 Verificação de ambiente Windows

Antes do Streamlit, `python -m fase4 doctor` agora inclui `pyarrow_runtime` e `altair_runtime`. O valor esperado com dependências completas é `ok`; valores `ausente` ou `falha ao importar` exigem correção do ambiente, pois o gráfico da aba Monitoramento usa Altair/PyArrow. Consulte [SETUP_WINDOWS.md](SETUP_WINDOWS.md). Isso **não substitui** o teste visual em um Windows real.
