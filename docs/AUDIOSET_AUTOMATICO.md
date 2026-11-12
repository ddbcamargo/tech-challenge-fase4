> **DOCUMENTO HISTÓRICO — v0.8.5.** O fluxo principal da v0.9.2 **não executa** preparação ou treinamento de áudio automaticamente. As instruções abaixo documentam uma versão anterior; para instalação atual consulte [README](../README.md) e [SETUP_WINDOWS.md](SETUP_WINDOWS.md).

# 🎙️ AudioSet automático — v0.8.5

## ✅ Objetivo

Substituir a sequência de comandos separados (`prepare-datasets`, `audioset-curate`, `audioset-fetch-authorized`, `audioset-train-category`) por **uma operação**. A interface sempre começa com um modelo local **treinado e identificado corretamente**; o treinamento real com AudioSet depende da disponibilidade e autorização dos WAVs.

### 🖥️ Inicialização simples (Windows / Git Bash)

```bash
cd /c/GITHUB/tech-challenge-fase4
source .venv/Scripts/activate
python -m pip install -e ".[all,test,downloader]"
python -m fase4 run
```

O `run`:

1. Prepara/valida os CSVs oficiais `balanced_train_segments.csv`, `eval_segments.csv` e `class_labels_indices.csv`, mais a amostra PhysioNet; respeita os hashes e reutiliza o que já existe.
2. Faz a curadoria estratificada, por **Speech, Breathing, Cough, Wheeze e Silence**, com semente 42; preserva uma seleção que já contenha WAVs.
3. Sem permissão para download de vídeos, **não tenta baixar vídeos do YouTube**. Não interpreta metadados como licença de download.
4. Se já existem pelo menos 12 WAVs válidos, separados e importados de `Speech` no split `balanced_train`, treina o modelo de referência real. Os splits `eval` **nunca entram no treinamento**.
5. Caso contrário, prepara um baseline de bancada `synthetic_demo` com 48 sinais artificiais, sem alegar uso de WAVs reais. **A UI mostra o aviso** e permite testar imediatamente o fluxo.
6. Gera dois WAVs artificiais em `data/demo/voice/` para testar sem upload; abre o Streamlit com opção de **gravar a própria fala** pelo microfone ou enviar WAV.
7. Reutiliza o modelo em execuções futuras; não sobrescreve um modelo real pronto com a demonstração.

### 📥 Quando você tem autorização para obter os trechos oficiais

**Vídeos locais já autorizados:**

```bash
python -m fase4 run \
  --source-dir data/fontes_autorizadas \
  --confirm-rights --limit 60
```

Os vídeos devem usar o ID do YouTube como nome de arquivo (`<youtube_id>.mp4`, `.webm`, `.wav`, etc.), conter a gravação **completa** correspondente e permitir o recorte pelos tempos do CSV. Uma pasta vazia não oferece nenhuma amostra.

**YouTube online:** use **somente se você efetivamente tem autorização para fazer download e utilizar os vídeos conforme as condições do YouTube e dos respectivos titulares**. A licença dos metadados do Google não substitui essa autorização.

```bash
python -m fase4 run \
  --online-authorized --confirm-rights --limit 60
```

O aplicativo tentará obter até 60 segmentos de `Speech`, converter com o FFmpeg incluído pelo `imageio-ffmpeg`, importar e treinar quando houver 12 ou mais WAVs distintos. Conteúdos removidos, bloqueados ou incompatíveis contam como **falhas**, não como exemplos de treinamento. O processamento online usa `yt-dlp` e pode exigir componentes adicionais (`ffprobe`) dependendo do formato.

**Outras categorias:** para preparar todas as categorias com WAVs autorizados:

```bash
python -m fase4 setup-audio --category all \
  --source-dir data/fontes_autorizadas --confirm-rights --limit 60
python -m fase4 run
```

`Silence` é utilizado como controle de silêncio, não como modelo Isolation Forest. As referências das outras categorias são treinadas em modelos separados (`models/audioset_cough.joblib`, etc.). O detector vocal principal usa `models/voice_anomaly.joblib` (categoria `Speech`).

### 🧪 Avaliar sem upload

Na aba **🎙️ Áudio**, clique em **▶️ Avaliar WAV de exemplo automaticamente (sem upload)**. É um sinal gerado por código **sem fala humana**, útil só para testar o pipeline de inferência e os alertas de qualidade. O resultado pode ser `outlier` por `CLIPPING` mesmo quando o Isolation Forest isolado considera `inlier`.

Para **avaliar uma fala real ou encenada**, use **🎤 Ou gravar uma fala fictícia**. O áudio será capturado a 16 kHz, sem precisar salvar manualmente no computador. Também é possível enviar um arquivo WAV. O Azure Speech + Language é opcional e só é chamado ao clicar em seu botão.

### 🔬 Verificar a origem do modelo

```bash
python -m fase4 doctor
python -m fase4 audioset-curated-status
```

| Campo `mode` | Origem efetiva |
|---|---|
| `synthetic_demo` | 48 sinais artificiais, nenhuma validade clínica |
| `audioset_speech_reference` | Características acústicas extraídas de WAVs associados aos IDs oficiais do split `balanced_train` |
| `audioset_cough_acoustic_reference` etc. | Modelo separado por categoria, quando houver WAVs suficientes |

O sistema registra hashes e origem declarada, mas não verifica automaticamente que a mídia baixada realmente corresponde à gravação histórica anotada pelo AudioSet. **Não afirmar desempenho clínico** a partir do score do Isolation Forest, nem afirmar que os rótulos `Speech`, `Cough` ou `Wheeze` são diagnósticos.

### 🛡️ Proteção e reproducibilidade

- O `.env` nunca é enviado ao repositório.
- Modelos gerados (`models/*.joblib`), clipes e dados brutos ficam fora do Git; o instalador cria o baseline quando necessário.
- O procedimento **não executa download online de vídeo sem autorização explícita**.
- O download dos índices CSV é permitido pela licença oficial; a mídia dos vídeos tem condições próprias.
- A ordem de seleção é reproduzível pela semente 42; downloads podem variar por disponibilidade/retirada de vídeos.
- Uma avaliação independente deve usar o split oficial `eval`, que precisa de WAVs separados e autorizados. Se o modelo de referência é sintético, não há avaliação do desempenho real.

**Fonte:** [Google AudioSet — Download](https://research.google.com/audioset/download.html).
