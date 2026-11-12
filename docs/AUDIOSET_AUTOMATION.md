# 🎧 AudioSet v0.8.4 — extração automática de trechos autorizados

## Por que precisamos obter os arquivos?

O AudioSet disponibiliza `balanced_train_segments.csv`, `eval_segments.csv`,
`class_labels_indices.csv` e *embeddings* pré-calculados, mas não distribui WAVs.
Cada linha contém `YTID`, `start_seconds`, `end_seconds`, `positive_labels`.
Nosso modelo da versão 0.8.2 extrai **características diretamente do WAV**;
assim, para manter esse pipeline, precisamos do áudio correspondente.

⚠️ **Direitos de acesso:** a licença CC BY 4.0 dos **metadados AudioSet** não é
uma licença universal dos vídeos. Os termos do YouTube restringem downloads e
acesso automatizado sem autorização aplicável. A automação desta versão exige
confirmação explícita do usuário, mas não verifica juridicamente essa autorização.
Não tenta contornar bloqueios, DRM, autenticação ou restrições da plataforma.
Para dados indisponíveis/não autorizados, use o corpus oficial de *embeddings*
ou outros áudios com direitos adequados.

Fontes: https://research.google.com/audioset/download.html e
https://www.youtube.com/t/terms .

## 🛠️ Instalação no Windows + Git Bash

```bash
cd /c/GITHUB/tech-challenge-fase4
source .venv/Scripts/activate
python -m pip install -e ".[all,test,downloader]"
python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
python -m yt_dlp --version
```

O FFmpeg será resolvido pelo pacote `imageio-ffmpeg` dentro do ambiente Python.
O comando global `ffmpeg` não precisa estar no PATH para processar fontes locais.
Para alguns fluxos online, o `yt-dlp` pode ainda exigir `ffprobe` externo.
**Nenhuma chave Azure é necessária** para esse fluxo.

## 📊 1. Curadoria oficial (sem mídia)

```bash
python -m fase4 prepare-datasets
python -m fase4 validate-datasets
python -m fase4 audioset-curate --seed 42 \
  --train-quota Speech=60 \
  --train-quota Breathing=40 \
  --train-quota Cough=40 \
  --train-quota Wheeze=40
python -m fase4 audioset-curated-status
```

Os números são **cotas-alvo**, não garantia de amostras: a seleção pode retornar
menos conforme a disponibilidade do CSV, coincidências de vídeo e rótulos.
O split `eval` permanece separado; nunca entra no treinamento.
Não altere a curadoria após importar WAVs: o programa impede substituir a seleção
com arquivos já existentes para evitar perda de rastreabilidade.

## 🔎 2. Prévia sem rede e sem gravação

```bash
python -m fase4 audioset-fetch-authorized --category Speech --limit 5
```

Mostra as IDs que seriam processadas. Nenhum download é feito sem `--download`.
Cada chamada tenta somente até `--limit` arquivos pendentes, no máximo 100.
A execução seguinte pula automaticamente os WAVs já importados.

## 📁 3A. Fontes locais autorizadas

Coloque vídeos/áudios originais autorizados em `data/fontes_autorizadas/` com
nome igual ao ID YouTube do manifesto, por exemplo `AAAAAAAAAAA.mp4`.
O arquivo precisa conter a **linha do tempo original** do vídeo, pois o FFmpeg
vai avançar até `start_seconds` e extrair até `end_seconds`.
Formatos aceitos `.mp4`, `.webm`, `.mkv`, `.m4a`, `.mp3`, `.wav`, `.ogg`.

```bash
python -m fase4 audioset-fetch-authorized --category Speech \
  --limit 20 --source-dir data/fontes_autorizadas \
  --download --confirm-rights --train-after
```

## ☁️ 3B. Vídeos do YouTube — SOMENTE com permissão aplicável

Se você **já tiver autorização específica para obter os vídeos também sob as
condições do YouTube**, poderá ativar o download via `yt-dlp`. A instalação
do pacote não concede direitos de acesso e alguns vídeos podem ter sido
excluídos/privatizados ou rejeitar o download.

```bash
python -m fase4 audioset-fetch-authorized --category Speech \
  --limit 20 --download --confirm-rights \
  --confirm-youtube-permission --train-after
```

O yt-dlp tenta obter apenas o segmento `[start_seconds,end_seconds]`, e o
FFmpeg converte para PCM16/mono/16kHz. O sistema rejeita segmentos com duração
incompatível (>0,25 s), mantém um arquivo por ID, sem duplicações, e anota
falhas sem interromper o lote.

**Não são utilizados bypass de autenticação, cookies, proxies nem contorno de
bloqueios.** Se não houver autorização, não execute esse modo.

## 🧠 4. Treinar e avaliar por categoria

Após obter pelo menos 12 WAVs de uma mesma categoria e do split treino:

```bash
python -m fase4 audioset-train-category Speech
python -m fase4 audioset-train-category Cough
python -m fase4 audioset-train-category Breathing
python -m fase4 audioset-train-category Wheeze
```

O argumento `--train-after` tenta automaticamente treinar a categoria da
execução, desde que tenham sido importadas 12+ amostras.
`Silence` é controle e não gera modelo.

Para avaliar sem contaminar o treinamento:

```bash
python -m fase4 audioset-fetch-authorized --category Speech --split eval --limit 8
# Proceda à importação do split eval somente se houver acesso permitido às mídias
python -m fase4 audioset-evaluate-category Speech
```

O resultado reporta taxa de *outliers* estatísticos, **não acurácia clínica**.
As classes AudioSet representam eventos acústicos, não diagnósticos de disartria
ou fadiga vocal. A fusão com Azure Speech/Language depende de WAVs com fala real.

## 🗂️ Persistência, auditoria e segurança

- `data/raw/audioset/stratified_clips/<split>/<categoria>/<clip_id>.wav`: WAVs.
- `data/raw/audioset/authorized_acquisitions.jsonl`: registros de importações
  (ID, fonte, horário UTC e SHA256; sem senhas/chaves Azure).
- `models/voice_anomaly.joblib` e `models/audioset_<categoria>.joblib`: modelos.
- `.gitignore` já exclui `data/raw/`, arquivos `.env` e modelos locais.
- O campo `source_verified=false` é mantido porque a aplicação não verifica
  independentemente a titularidade e o conteúdo semântico das gravações.

## 🧪 Testes e limites da validação

Os testes automatizados cobrem o modo prévia, controle de permissões, conversão
FFmpeg de arquivos locais autorizados, retomada, registro de falhas, treinamento
com 12 WAVs simulados e isolamento da avaliação. **Não incluímos vídeos
baixados do YouTube nos testes**, nem alegamos performance clínica.

## 🧰 FFmpeg no Python — sem instalação global (v0.8.4)

O extra `downloader` agora instala `imageio-ffmpeg`, que carrega um executável
FFmpeg distribuído no wheel. A classe `AuthorizedAudioSetFetcher` chama diretamente
o caminho retornado por `get_ffmpeg_exe()` para recorte e conversão PCM16.
Por isso, não precisa instalar FFmpeg no PATH do Windows para processar vídeos
locais autorizados.

Validação no Git Bash:

```bash
python -m pip install -e ".[all,test,downloader]"
python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_version())"
python -m fase4 audioset-fetch-authorized --category Speech --limit 5
```

**Observação:** `imageio-ffmpeg` empacota o `ffmpeg`, mas geralmente não o
`ffprobe`. Alguns recursos online de `yt-dlp` podem exigir `ffprobe`
instalado separadamente. O suporte online permanece condicionado à autorização
da plataforma e dos titulares; não há contorno de restrições.
