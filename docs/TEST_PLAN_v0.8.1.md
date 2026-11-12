# ✅ Roteiro de testes — versão 0.8.1 (Google AudioSet)

## 1. Ambiente (Windows 11 / Git Bash)

```bash
cd /c/GITHUB/tech-challenge-fase4
source .venv/Scripts/activate
python -m pip install -e ".[all,test]"
python -m pytest -q
python -m fase4 doctor
```

Resultado local esperado: **52 testes aprovados**. O teste é offline, não
consome Azure e não descarrega áudio do YouTube.

## 2. Dados oficiais

```bash
python -m fase4 prepare-datasets
python -m fase4 validate-datasets
```

Esperado: `ready: true`, incluindo **quatro** arquivos oficiais: PSV
PhysioNet, AudioSet `balanced_train_segments.csv`, `eval_segments.csv` e
`class_labels_indices.csv`. Caso os três arquivos da v0.8 já existam, o
quarto deve ser adicionado sem sobrescrever os demais.

## 3. Seleção e importação (Google AudioSet)

```bash
python -m fase4 audioset-select --label Speech --split balanced_train --limit 24
python -m fase4 audioset-status
```

Esperado: `selected: 24`, `available: 0`, `source_verified: false`.
A opção cria um manifesto com origem/tempo/rótulos, **não baixa WAVs**.

No Streamlit (`python -m fase4 run`), na aba Áudio: veja a tabela, abra os
links da origem, obtenha os trechos cujo uso é permitido e recorte exatamente
os intervalos. Para um exemplo de conversão de um vídeo já autorizado:

```bash
ffmpeg -ss 30 -i arquivo_autorizado.mp4 -t 10 -ac 1 -ar 16000 -c:a pcm_s16le trecho.wav
python -m fase4 audioset-import-clip ID_EXATO trecho.wav
```

Substitua o ID e os segundos pelo trecho mostrado no `status`. Repita com
12 vídeos/IDs diferentes, se disponíveis. Após isso, execute:

```bash
python -m fase4 voice-train-audioset
python -m fase4 doctor
```

Esperado: `mode: audioset_speech_reference`, `reference_count: >=12`,
proveniência de AudioSet no arquivo `models/voice_anomaly.json`. Os resultados
continuam sendo acústicos, sem validação clínica.

Se não conseguir obter 12 trechos autorizados, **não use arquivos aleatórios
chamados com IDs AudioSet**: isso invalidaria a procedência. Registre a
indisponibilidade e use a demo sintética apenas como prova de funcionamento.

## 4. Demais módulos que devemos testar juntos

- **Fisiologia/PhysioNet:** importar PSV e executar replay/alertas na aba 2.
- **Modelo local:** analisar WAV de avaliação separado dos trechos de treino;
  avaliar score e flags técnicas, não sintomas.
- **Azure:** executar a transcrição de WAV de **consulta fictícia encenada**,
  não do AudioSet sem contexto clínico, usando o `.env` local; ver transcrição,
  sentimento, entidades e histórico.
- **Vídeo:** baixar MediaPipe Lite, inspecionar MP4 autorizado e analisar
  ângulos de joelhos/cotovelos.
- **Alertas:** conferir avisos, revisão humana e persistência no SQLite.

Consulte [AZURE_VALIDATION.md](AZURE_VALIDATION.md) para erros de Speech e
Language. Nunca compartilhe `.env`, chaves, vídeos ou dados de pessoas reais.
