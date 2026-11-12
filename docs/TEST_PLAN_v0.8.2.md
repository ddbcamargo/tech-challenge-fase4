# 🧪 Roteiro de testes — Tech Challenge v0.8.2

## 1. Ambiente (Windows Git Bash)

Preserve `.venv`, `.env`, `data` e `models` durante a atualização:

```bash
cd /c/GITHUB/tech-challenge-fase4
source .venv/Scripts/activate
python -m pip install -e ".[all,test]"
python -m pytest -q
python -m fase4 doctor
python -m fase4 prepare-datasets
python -m fase4 validate-datasets
```

## 2. Curadoria estratificada oficial

```bash
python -m fase4 audioset-curate --seed 42
python -m fase4 audioset-curated-status
```

Observe cinco categorias nos splits `balanced_train` e `eval`, totais,
intervalos e URLs. **A seleção não baixa o áudio.** Confira a ausência de
repetição de IDs. Uma segunda seleção com a mesma semente deve gerar os
mesmos IDs enquanto não houver WAVs importados; após importar WAVs, a
reseleção é bloqueada para protegê-los.

## 3. Importação de arquivos reais autorizados

1. Abra uma das URLs retornadas e confirme a identidade do vídeo e os
   direitos para obter/usar um trecho da gravação.
2. Recorte **exatamente o intervalo oficial** e converta para WAV mono,
   PCM16, 16 kHz. Se o vídeo de origem for seu, você pode usar ffmpeg:

```bash
ffmpeg -ss INICIO_SEGUNDOS -i video_autorizado.mp4 -t DURACAO_SEGUNDOS \
  -ac 1 -ar 16000 -c:a pcm_s16le arquivo.wav
python -m fase4 audioset-curated-import ID_EXATO arquivo.wav --confirm-rights
```

3. Repita a importação até possuir 12 WAVs de **uma mesma categoria** no
   `balanced_train`. Não misture arquivos de treino e `eval`, e não associe
   áudios inventados a um ID oficial.
4. Execute `python -m fase4 audioset-train-category Speech` (ou Breathing,
   Cough ou Wheeze, se tiver 12 amostras dessa categoria).
5. Para avaliar, importe WAVs separados do `eval` e use:

```bash
python -m fase4 audioset-evaluate-category Speech
```

A taxa de outliers é somente a proporção de desvios apontados pelo modelo,
**não** sua acurácia clínica nem sua capacidade de detectar disartria.

## 4. Verificação visual completa

```bash
python -m fase4 run
```

Na aba **🎙️ Áudio**, encontre a curadoria estratificada, o quadro com
categorias, os links, o upload, o treino específico e o botão de avaliação.
Teste novamente o fluxo de transcrição com Azure e verifique a aba de
alertas e os históricos. Não envie sinais sintéticos de teste ao Azure.

## 5. O que foi automatizado

- Seleção reprodutível multiclasse com CSVs simulados no formato AudioSet;
- Deduplicação de vídeos entre categorias e splits;
- Detecção de cotas insuficientes;
- Recusa de WAV inválido, duplicado ou de duração incorreta;
- Isolamento do treino `balanced_train` e avaliação `eval`;
- Treinamento e inferência demonstrativos com áudios artificiais locais.

**Não foram executados** download de WAVs reais do Google, teste de um
modelo treinado com o AudioSet verdadeiro ou teste real de Azure nesta
entrega. Esses passos dependem dos arquivos autorizados e das chaves locais.
