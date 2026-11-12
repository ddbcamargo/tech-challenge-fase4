# 🩺 Tech Challenge — Fase 4

**Protótipo acadêmico de monitoramento multimodal de pacientes fictícios.**

`Python 3.12+` · `Monólito modular / Clean Architecture` · `SQLite` · `PhysioNet` · `AudioSet` · `Azure` · `MediaPipe` · `Isolation Forest`

**Versão 0.8.5 — Áudio em um fluxo: preparar datasets oficiais, selecionar categorias, obter mídias autorizadas quando possível, treinar e avaliar diretamente no Streamlit.**

Este projeto é totalmente novo: nenhum código, estrutura ou base de pacientes
foi reutilizado da Fase 3.

> Não usar em assistência médica real. Eventos e alertas são experimentais,
> não equivalem a diagnóstico ou recomendação de tratamento.



## ⚡ v0.8.5 — Apenas instalar e executar

O projeto agora **prepara o detector de áudio automaticamente**. Não é necessário executar quatro comandos diferentes nem criar uma pasta de vídeos vazia.

```bash
cd /c/GITHUB/tech-challenge-fase4
source .venv/Scripts/activate
python -m pip install -e ".[all,test,downloader]"
python -m fase4 run
```

Esse comando prepara os índices oficiais do **Google AudioSet**, realiza a curadoria por categoria e treina o modelo principal com WAVs reais já importados, se houver ao menos 12. **Sem WAVs oficiais, deixa um modelo `synthetic_demo` treinado automaticamente**, com aviso visível; esse modelo é **somente uma demonstração**, não treinamento em fala real nem validação clínica. O programa não obtém vídeos do YouTube sem sua autorização explícita.

**Um único comando para permitir obtenção e treinamento de WAVs, caso você tenha autorização:**

```bash
# Vídeos autorizados já existentes, nomeados com o YouTube ID:
python -m fase4 run --source-dir data/fontes_autorizadas --confirm-rights --limit 60

# Somente se houver autorização aplicável também para baixar do YouTube:
python -m fase4 run --online-authorized --confirm-rights --limit 60
```

Na aba **🎙️ Áudio**, você pode clicar **▶️ Avaliar WAV de exemplo automaticamente (sem upload)**, enviar um WAV próprio ou **🎤 gravar uma fala fictícia**. O painel identifica claramente se o modelo está em modo demo ou AudioSet real. Os resultados locais são persistidos no SQLite. Os serviços Azure só são chamados quando solicitados.

👉 Consulte [**Guia completo do áudio automático**](docs/AUDIOSET_AUTOMATICO.md) e [**Plano de testes v0.8.5**](docs/TEST_PLAN_v0.8.5.md). As instruções de comandos antigos abaixo permanecem como procedimentos avançados/opcionais.

## 🛠️ v0.8.4 — FFmpeg instalado pelas dependências Python

Agora `python -m pip install -e ".[all,test,downloader]"` instala também `imageio-ffmpeg`,
que inclui um binário FFmpeg para Windows, Linux e macOS. O pipeline de aquisição
usa `imageio_ffmpeg.get_ffmpeg_exe()` em vez de exigir `ffmpeg` no `PATH`.

> **Atenção:** `ffmpeg -version` ainda pode responder `command not found` no Git Bash.
> Isso é esperado: o executável fica dentro do ambiente Python, e não como comando global.
> Confira com:
>
> ```bash
> python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
> ```
>
> Para alguns fluxos online do `yt-dlp` poderá ser necessário `ffprobe` externo;
> baixar mídia requer autorização conforme a plataforma e os titulares.

## 🎧 v0.8.3 — Preparação automatizada de WAVs autorizados do AudioSet

O AudioSet **fornece IDs de vídeo, segundos e rótulos, mas não os áudios originais**.
A partir da v0.8.3, `audioset-fetch-authorized` automatiza recorte, conversão
para WAV 16 kHz/mono/PCM16, importação na curadoria, relatório de falhas e retomada.
O processo é limitado a fontes com direitos de uso e download efetivamente permitidos;
metadados públicos não significam permissão para baixar os vídeos do YouTube.

```bash
# 1. Preparar os dados oficiais e selecionar os trechos
python -m fase4 prepare-datasets
python -m fase4 audioset-curate --seed 42 --train-quota Speech=60 --train-quota Cough=40 --train-quota Breathing=40 --train-quota Wheeze=40

# 2. Ver a seleção e os IDs, SEM baixar nada
python -m fase4 audioset-fetch-authorized --category Speech --limit 10

# 3A. Fonte local que você possui/permissão: os vídeos se chamam <youtube_id>.mp4 (ou outra extensão suportada)
python -m fase4 audioset-fetch-authorized --category Speech --limit 20 --source-dir "data/fontes_autorizadas" --download --confirm-rights --train-after

# 3B. Apenas se houver autorização aplicável para baixar do YouTube:
python -m pip install -e ".[all,test,downloader]"
python -m fase4 audioset-fetch-authorized --category Speech --limit 20 --download --confirm-rights --confirm-youtube-permission --train-after

# 4. Verificar o total disponível, retomar lote e avaliar com WAVs do split eval
python -m fase4 audioset-curated-status
python -m fase4 audioset-evaluate-category Speech
```

O `imageio-ffmpeg` substitui a instalação global de FFmpeg nos fluxos locais.
As etapas 3A e 3B exigem a existência de fontes autorizadas; sem elas, use os *embeddings* oficiais do Google como
alternativa para um pipeline que não depende de vídeos. A avaliação só é possível
após importar amostras do split `eval`; resultados não são diagnóstico clínico.
Leia `docs/AUDIOSET_AUTOMATION.md` para o fluxo completo, limitações e segurança.

## 🎯 Novo na v0.8.2: seleção por categoria AudioSet

O índice oficial é **multirrótulo**: um mesmo trecho pode conter fala e respiração.
O projeto escolhe uma **categoria de referência** por trecho, sem descartar os demais rótulos.
A seleção prioriza candidatos com menos sobreposições nas cinco categorias e usa
**semente 42** para reprodutibilidade. Nenhum vídeo é repetido entre treino e avaliação.

| Categoria oficial | Treino (selecionados) | Avaliação (selecionados) | Destino |
|---|---:|---:|---|
| `Speech` | 24 | 8 | Referência vocal (modelo principal) |
| `Breathing` | 16 | 6 | Modelo acústico separado de respiração |
| `Cough` | 16 | 6 | Modelo acústico separado de tosse |
| `Wheeze` | 16 | 6 | Modelo acústico separado de chiado |
| `Silence` | 8 | 6 | Controle acústico; não treina Isolation Forest |

Estas são **cotas solicitadas**, não garantia de disponibilidade. O painel e CLI
registram faltas quando não há segmentos suficientes. **Selecionar IDs não baixa
nem treina áudios.** Cada modelo requer ao menos **12 WAVs reais importados
para a sua categoria**, e somente do `balanced_train`; o `eval` mede taxa de
desvios em áudios separados, não acurácia ou sensibilidade clínica.

```bash
python -m fase4 prepare-datasets
python -m fase4 audioset-curate --seed 42
python -m fase4 audioset-curated-status
# Após verificar os direitos do vídeo, obter e preparar o WAV correto:
python -m fase4 audioset-curated-import ID_EXATO arquivo.wav --confirm-rights
# Repetir até 12 WAVs de uma mesma categoria:
python -m fase4 audioset-train-category Speech
# Opcional: importar WAVs de eval e avaliar desvios separadamente:
python -m fase4 audioset-evaluate-category Speech
python -m fase4 run
```

No Streamlit, consulte **🎙️ Áudio → Curadoria AudioSet estratificada**, o quadro de
quantidades, os links dos trechos, a importação e os botões de treino/avaliação.
Leia a explicação em [docs/AUDIOSET.md](docs/AUDIOSET.md) e os testes em
[docs/TEST_PLAN_v0.8.2.md](docs/TEST_PLAN_v0.8.2.md).

**Não misturamos os cinco tipos num único Isolation Forest:** uma tosse não é
uma fala anormal por definição. Modelos separados com essas amostras fazem
comparações acústicas por categoria; **não são classificadores de eventos**, nem
diagnósticos de disartria, fadiga ou dificuldade respiratória. A qualidade
estatística só poderá ser examinada com WAVs independentes e verificação manual
das fontes.

## 🚀 Comece aqui: um fluxo, poucos comandos

Requer Python 3.12. Abra um terminal na raiz do projeto:

```bash
python -m venv .venv
```

Ative o ambiente:

- **Windows Git Bash (MINGW64):** `source .venv/Scripts/activate`
- **Windows PowerShell:** `.venv\Scripts\Activate.ps1`
- **Linux/macOS:** `source .venv/bin/activate`

Instale os pacotes:

```bash
python -m pip install -e ".[all,test]"
```

Se for usar Azure, configure o arquivo `.env` **uma única vez**, somente no
seu computador (veja [docs/AZURE.md](docs/AZURE.md)):

```bash
cp .env.example .env
notepad .env
```

Preencha as duas chaves, a região Speech e o endpoint Language localmente.
**Nunca cole chaves no chat, em commits ou no `.env.example`.** A versão 0.6
carrega automaticamente `.env` ao executar CLI, Streamlit ou API. Se já possui
um `.env`, **não execute `cp` novamente**: basta editá-lo.

Verifique as dependências e integrações:

```bash
python -m fase4 doctor
```

Baixe e valide os quatro arquivos oficiais pequenos (1 PSV + 3 CSVs):

```bash
python -m fase4 prepare-datasets
python -m fase4 validate-datasets
```

**Para usar a aplicação, o comando principal continua sendo somente:**

```bash
python -m fase4 run
```

Esse comando prepara automaticamente o SQLite com 25 pacientes fictícios
(sem recriá-los quando já existem) e abre o dashboard Streamlit.
O painel agora tem um assistente de dados integrado: na aba **📦 1. Dados**,
clique em **Preparar amostras oficiais** e **Carregar amostra PhysioNet neste caso**.
Na aba **⏯️ 2. Replay temporal**, avance uma hora por clique e acompanhe
a curva, as medições e os alertas. Na aba **🚨 5. Alertas**, revise as evidências.

Nas etapas 0.7 e 0.8, a aba **🎙️ 3. Áudio** permite treinar/consultar um detector acústico local e executa a transcrição de **uma fala curta**
com Azure Speech, seguida de sentimento, frases-chave e entidades pelo Azure
Language, e consulta o histórico persistido em SQLite. Também inspeciona WAV
localmente sem
credenciais Azure; a aba **🎥 4. Vídeo** pode baixar o modelo MediaPipe Lite
oficial e analisar um MP4 enviado pela equipe.

Se você já preparou as amostras pelo terminal, pode pular o primeiro botão.

> A preparação dos datasets exige internet **apenas na primeira vez**; o painel
> e os testes continuam funcionando sem esse download. Não há download de
> vídeos do YouTube ou de grandes bases completas.

## 🧭 O que executar e quando

| Quando | Comando ou ação | Resultado |
|---|---|---|
| 🛠️ Uma vez, antes de começar | `pip install -e ".[all,test]"` | Instala o ambiente |
| 🔐 Uma vez, após criar serviços Azure | `cp .env.example .env` e `notepad .env` | Guarda chaves só no PC; o programa as carrega automaticamente |
| 🔎 Após instalar ou se houver problema | `python -m fase4 doctor` | Mostra dependências e configurações faltantes |
| 📥 Uma vez, com internet | `python -m fase4 prepare-datasets` | Baixa fontes oficiais com registro da origem |
| ✅ Após baixar, sem internet | `python -m fase4 validate-datasets` | Confere formato, integridade e quantidades |
| **▶️ Sempre que for usar a aplicação** | **`python -m fase4 run`** | Prepara banco e inicia o painel |
| 📦 Dentro do painel, aba 1 | Preparar e carregar amostra oficial | Preenche o banco e mostra medições |
| ⏯️ Dentro do painel, aba 2 | Reproduzir próxima hora | Atualiza gráfico e registra novos alertas |
| 🎙️ Dentro do painel, aba 3 | Selecionar trechos AudioSet, importar WAVs autorizados, treinar modelo ou testar demo sintética, opcionalmente Azure | Score acústico, rastreabilidade da fonte, transcrição quando configurada |
| 🎥 Dentro do painel, aba 4 | Preparar modelo e enviar MP4 | Ângulos de joelho/cotovelo e desvios |
| 🚨 Dentro do painel, aba 5 | Examinar e marcar alerta revisado/descartado | Evidências e decisão humana persistida |
| 🔌 Só para desenvolvedores | `python -m fase4 api` | Inicia API HTTP opcional |
| 🧪 Após alterações no código | `python -m pytest -q` | Testa o núcleo sem Azure nem Streamlit |

**Não é necessário executar cada arquivo `.py` manualmente.** CLI, dashboard e
API chamam o mesmo serviço da camada de aplicação.

## 🔊 Etapa 0.8.1 — Google AudioSet como referência oficial prioritária

**O enunciado sugere o AudioSet para áudio.** Agora o projeto faz mais do que
listar rótulos: importa o CSV oficial `balanced_train_segments.csv`, seleciona
**trechos rotulados como `Speech`**, exibe links de origem e seus intervalos,
aceita WAVs correspondentes obtidos **com autorização**, confere formato/duração
e treina nosso **Isolation Forest** com no mínimo 12 trechos importados.

O treinamento registra no manifesto do modelo o split, rótulo, checksum do
índice/seleção e hashes dos arquivos de áudio. **Os CSVs não são os áudios**;
Google não publica todos os trechos como WAV diretamente. A correspondência
real de um WAV fornecido pelo usuário com o vídeo de origem precisa ser
verificada manualmente; o programa valida o cadastro e a duração, mas **não
certifica a autenticidade do som**. Os direitos de uso dos vídeos são distintos
da licença dos metadados AudioSet.

### 🪟 Fluxo simples pelo Streamlit

1. Na aba **📦 Dados**, clique **Preparar amostras oficiais** (ou use `prepare-datasets`).
2. Na aba **🎙️ Áudio**, clique **Selecionar 24 trechos oficiais de fala**.
3. Na tabela, abra os links e confira os intervalos. Obtenha os segmentos com
   autorização, converta para **WAV PCM16 mono 16 kHz** e importe-os um por vez,
   declarando que correspondem ao segmento selecionado.
4. Quando houver **12 ou mais WAVs de fala**, clique **Treinar Isolation Forest com
   AudioSet**. O resultado deve mostrar `audioset_speech_reference` como origem.
5. Analise um WAV **separado do conjunto de treinamento**, no botão local ou no
   fluxo Azure, e veja o resultado no histórico. Não inferimos disartria de
   uma classificação `outlier`.

### ⌨️ Equivalente no Git Bash

```bash
python -m fase4 prepare-datasets
python -m fase4 validate-datasets
python -m fase4 audioset-select --label Speech --split balanced_train --limit 24
python -m fase4 audioset-status
# Após obter legalmente o WAV do intervalo indicado no status:
python -m fase4 audioset-import-clip ID_DA_TABELA caminho/do/trecho.wav
# Repita a importação para ao menos 12 IDs distintos
python -m fase4 voice-train-audioset
python -m fase4 run
```

O projeto **não baixa vídeos do YouTube automaticamente** nem inclui WAVs
protegidos no pacote. Se os segmentos não estiverem disponíveis, a preparação
de CSV funciona mesmo assim, mas o treino AudioSet fica indisponível até que
você obtenha material utilizável. A seleção só deve conter áudios obtidos
legalmente. Para criar um WAV a partir de arquivo de vídeo já autorizado:

```bash
ffmpeg -ss 30 -i arquivo_autorizado.mp4 -t 10 -ac 1 -ar 16000 -c:a pcm_s16le trecho.wav
```

Substitua `30` pelo `start_seconds` e `10` pela diferença entre `end_seconds` e
`start_seconds` do trecho escolhido. Consulte [docs/AUDIOSET.md](docs/AUDIOSET.md),
[docs/DATASETS.md](docs/DATASETS.md) e o [roteiro de testes 0.8.1](docs/TEST_PLAN_v0.8.1.md).

## 🧠 Etapa 0.8 — Modelo próprio de detecção acústica

**Implementamos treinamento real de um modelo local com `StandardScaler` +
`IsolationForest`**, utilizando características de energia, silêncio, saturação,
espectro e periodicidade estimada do sinal. A análise roda **sem Azure**,
persiste o resultado no SQLite e produz alerta informativo quando encontra
um desvio estatístico ou problema de qualidade do arquivo. A saída separa
`ml_prediction` dos avisos determinísticos (`quality_flags`), sem atribuir
diagnóstico clínico. **O modelo foi testado com sinais artificiais, não com
um corpus clínico rotulado.**

Para testar do zero com **dois WAVs gerados automaticamente**, use no Git Bash:

```bash
python -m fase4 voice-train-demo
python -m fase4 voice-demo-files
python -m fase4 init
python -m fase4 voice-analyze data/demo/voice/sinal_sintetico_referencia.wav --patient TC4-P001
python -m fase4 voice-analyze data/demo/voice/sinal_sintetico_alterado.wav --patient TC4-P001
python -m fase4 run
```

Ou apenas `python -m fase4 run` e, na aba **🎙️ Áudio**, clique
**Treinar referência sintética**, **Gerar 2 WAVs** e faça upload para
**Analisar WAV com modelo local**. Os WAVs sintéticos **não contêm fala**:
**não os envie ao Speech-to-Text**. Para testar Azure, envie outra gravação
**encenada contendo uma pessoa falando** (PCM16 mono, 16 kHz, até 30 s).
O processamento Azure acrescentará o resultado vocal local, se o modelo
estiver treinado.

Para treinar com 12–100 WAVs autorizados (não clínicos e separados do áudio
de avaliação), use `python -m fase4 voice-train-references data/raw/voice_references`.
Isso **substitui** o modelo anterior; o experimento não valida disartria ou
fadiga vocal. O arquivo do modelo e os WAVs de teste são ignorados pelo Git.

📘 [Documentação técnica do treinamento e limitações](docs/VOICE_ANOMALIES.md)  
✅ [Roteiro de testes completo (incluindo Azure, vídeo e vitais)](docs/TEST_PLAN_v0.8.md)  
☁️ [Checklist do Azure real](docs/AZURE_VALIDATION.md)  
📊 [Resultados locais verificáveis da v0.8](docs/RESULTS_v0.8.md)  
📊 [Resultados e limites da v0.8.1](docs/RESULTS_v0.8.1.md)

## ☁️ Etapa 0.7 — integração real de áudio + histórico

**O que entregamos no código (40 testes locais aprovados):**

1. **Speech-to-Text:** reconhecimento de uma fala curta em português do Brasil,
   com mensagens de falha para ausência de fala, cancelamento e problemas de acesso.
2. **Azure Language:** análises de sentimento, frases-chave e entidades no texto
   transcrito, sem interpretação clínica.
3. **Histórico persistido:** o SQLite guarda a transcrição e os resultados,
   vinculados a um *caso fictício*. O dashboard consulta esse histórico após
   reiniciar; novos downloads não são necessários para visualizá-lo.
4. **Diagnóstico seguro:** as exceções da nuvem não exibem chaves, tokens ou
   detalhes brutos; os testes usam apenas substitutos de SDKs sem gastar cota.

**Para executar depois de configurar seu `.env`:**

```bash
python -m fase4 doctor
python -m fase4 run
```

Na aba **🎙️ 3. Áudio**, envie um WAV fictício, opcionalmente inspecione-o e
clique em **☁️ Transcrever e analisar com Azure**. Abaixo dos botões,
confira o **📋 Histórico de análises Azure**. Não envie áudio de pacientes reais.

**Ainda pendente:** testar as chamadas reais com sua assinatura no Windows.
O teste automatizado confirma os contratos e o banco, **não** prova que a chave
funciona nem que um WAV será reconhecido. Consulte
[docs/AZURE_VALIDATION.md](docs/AZURE_VALIDATION.md).

## ⏯️ Etapa 0.4 — o que muda no painel

O Streamlit deixa de depender de um upload manual antes de mostrar resultados.
Nesta versão o fluxo principal tem **três ações**, todas na interface:

1. **📦 Dados:** obtenha as amostras oficiais (se ainda não estão na pasta)
   e carregue um PSV no caso fictício `TC4-P001`.
2. **⏯️ Replay temporal:** clique em **Reproduzir próxima hora** para avançar
   a série histórica. O gráfico cresce hora a hora; só as medições já
   apresentadas entram no cálculo de desvios. A fonte selecionada é isolada.
3. **🚨 Alertas:** consulte evidências e marque cada ocorrência como
   **revisada** ou **descartada**. A decisão fica registrada no SQLite.

O botão **Voltar ao início do replay** reinicia a navegação da sessão, **não
apaga alertas já gravados**. Reproduzir novamente não duplica os mesmos eventos.

> É um replay **manual de dados históricos**, não monitoramento hospitalar
> em tempo real. Para entender cada passo e as decisões de implementação, veja
> [docs/REPLAY.md](docs/REPLAY.md).

## 🎙️🎥 Etapa 0.5 — áudio e vídeo

**Áudio (sem Azure):** envie um WAV PCM16 curto, clique em **Inspecionar WAV
localmente** e examine duração, intensidade, períodos de baixa energia e
amostras saturadas. São descritores físicos, **não** diagnóstico de alterações
na voz. O índice AudioSet oficial aparece como exemplos de classes de fala,
mas não contém transcrições de consultas médicas.

**Áudio (com Azure):** configure Speech + Language no seu ambiente e clique
em **☁️ Transcrever e analisar com Azure** para obter transcrição, sentimento textual,
termos e entidades. Use uma gravação **encenada**, com até 30 segundos, em
WAV mono PCM 16-bit, 16 kHz. Não coloque as chaves no repositório.

**Vídeo:** clique em **Preparar modelo MediaPipe Lite** uma única vez,
envie MP4 curto (até 2 minutos e 60 MiB) e clique em **Analisar postura**.
O modelo é obtido da fonte oficial do Google e guardado em `models/`, fora
do Git. O gráfico acompanha ângulos estimados em joelhos e cotovelos.

Comandos equivalentes de diagnóstico no terminal:

```bash
python -m fase4 prepare-pose-model
python -m fase4 inspect-wav data/raw/consulta_encenada.wav --patient TC4-P001
python -m fase4 inspect-video data/raw/fisioterapia.mp4
```

Os dois últimos comandos só funcionam **depois de você fornecer os arquivos**
locais nos caminhos indicados. Para conversão de WAV, limitações, consentimento
e integração Azure, veja [docs/MEDIA.md](docs/MEDIA.md).

## 📦 Etapa 0.3 — dados oficiais e rastreabilidade

`prepare-datasets` traz **somente estes quatro arquivos** para `data/raw/official/`:

| Base | Arquivo | Finalidade |
|---|---|---|
| 🫀 PhysioNet 2019 | `p100679.psv` | Série horária real, usada exclusivamente em replay acadêmico |
| 🏋️ Google AudioSet | `balanced_train_segments.csv` | Índice de segmentos usados para a seleção de treino de fala |
| 🔊 Google AudioSet | `eval_segments.csv` | Índice separado de avaliação de eventos sonoros (sem rótulos de doenças) |
| 🏷️ Google AudioSet | `class_labels_indices.csv` | Nomes das classes acústicas do índice |

O arquivo local `data/raw/official/manifest.json` registra o endereço oficial,
licença, data e SHA-256 de cada download. A validação identifica arquivos
ausentes, alterados e formatos inconsistentes. O download é idempotente:
**não sobrescreve um arquivo modificado ou sem procedência verificada**.

Os dados brutos e o manifesto são ignorados pelo Git. Por segurança,
reproduzimos **uma série pública por vez** no caso fictício, e cada origem tem
identificação própria no SQLite; nenhuma série é considerada pertencente ao
paciente fictício.

### ⌨️ Comandos opcionais para dados

Caso queira processar dados pelo terminal em vez da interface:

```bash
# Inicializa banco sem abrir o navegador
python -m fase4 init

# Após executar prepare-datasets (ou baixar manualmente um PSV oficial)
python -m fase4 import-physionet data/raw/official/p100679.psv --patient TC4-P001

# Recalcula outliers de sinais vitais e mudanças de prescrições fictícias
python -m fase4 scan all --patient TC4-P001

# Exibe alertas e suas evidências
python -m fase4 alerts --patient TC4-P001

# Inspeciona o índice CSV oficial do AudioSet, sem baixar vídeos do YouTube
python -m fase4 audioset-preview data/raw/official/eval_segments.csv --limit 5
```

## 🗂️ Datasets: a prioridade é a do enunciado

1. **PhysioNet:** [Challenge 2019](https://physionet.org/content/challenge-2019/1.0.0/).
   Fonte principal de séries de sinais vitais, em formato PSV (CC BY 4.0).
2. **Google AudioSet:** [site oficial](https://research.google.com/audioset/).
   Primeiro recurso para eventos acústicos. O sistema agora permite selecionar
   trechos oficiais, importar WAVs autorizados e treinar o detector com a classe
   `Speech`; não baixa automaticamente áudio dos vídeos associados.
3. **Vídeo:** como o enunciado não define uma base de vídeos, candidato
   [KIMORE](https://pubmed.ncbi.nlm.nih.gov/31217121/) (acesso aos vídeos RGB
   sujeito à autorização dos pesquisadores) ou gravações encenadas e
   consentidas pela equipe.
4. **Pacientes/prescrições/consultas:** tudo criado especificamente para a
   Fase 4 com dados e roteiros fictícios.

O AudioSet **não é uma base de consultas médicas**. Se não fornecer exemplos
apropriados ao objetivo de fala, usaremos áudios encenados para a demonstração
e documentaremos a limitação. Não confundiremos sentimento textual com disartria.

Uma série pública de sinais vitais pode ser vinculada a `TC4-P001` apenas para
reprodução acadêmica. Isso **não** significa que o paciente fictício seja a
pessoa de origem do registro, nem que áudio/vídeo e sinais vitais pertençam
realmente ao mesmo indivíduo.

## 🔐 Credenciais Azure e modelo de postura

As abas de áudio/vídeo mostram claramente quando uma integração não está
configurada. Configure estas variáveis **no seu `.env` local**, usando
`.env.example` apenas como modelo público:

- `AZURE_SPEECH_KEY` e `AZURE_SPEECH_REGION`;
- `AZURE_LANGUAGE_KEY` e `AZURE_LANGUAGE_ENDPOINT`;
- `POSE_MODEL_PATH` apontando para o arquivo `.task` do
  [MediaPipe Pose Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python).

Não envie chaves para o repositório, nem as adicione ao `.env.example`. O
projeto carrega automaticamente o arquivo `.env` **da raiz do projeto**, mesmo
quando iniciado por CLI, Streamlit ou API. Configurações exportadas no terminal
têm prioridade sobre os valores do arquivo. `python -m fase4 doctor` informa
apenas se as credenciais estão presentes, **sem mostrar seus valores**.

Os recursos Azure configurados para o desafio são `speech-tc4` e
`language-tc4`, ambos no grupo `rg-tech-challenge-fase4` e plano **Free F0**.
O acesso e a primeira chamada Azure **ainda precisam ser testados no ambiente
local da equipe**. Veja o passo a passo em [docs/AZURE.md](docs/AZURE.md) e o checklist de
validação em [docs/AZURE_VALIDATION.md](docs/AZURE_VALIDATION.md).

A transcrição Azure implementada atualmente é para **WAV curto**; áudios
extensos exigirão a API de transcrição em lote ou contínua. `POSE_MODEL_PATH`
é opcional: sem ele, usamos `models/pose_landmarker_lite.task` quando preparado
pelo botão ou pelo comando `prepare-pose-model`.

## 🏗️ Arquitetura adotada

**Monólito modular com camadas inspiradas em Clean Architecture / Ports & Adapters.**

| Camada | Pasta | O que faz |
|---|---|---|
| Domínio | `fase4/domain/` | Regras puras de anomalias e sinais textuais |
| Aplicação | `fase4/application/` | Casos de uso e contratos (ports) |
| Infraestrutura | `fase4/infrastructure/` | SQLite, PhysioNet, AudioSet, Azure, MediaPipe |
| Preparação de dados | `fase4/infrastructure/datasets/catalog.py` | Download limitado, manifesto, checksum e validação |
| Curadoria acústica | `fase4/infrastructure/datasets/audioset_samples.py` | Seleção de segmentos oficiais, importação de WAVs e rastreabilidade |
| Interfaces | `fase4/interfaces/` | CLI, Streamlit e API HTTP |
| Composição | `fase4/container.py` | Liga casos de uso aos adaptadores concretos |
| Entrada única | `fase4/__main__.py` | Comandos `python -m fase4 ...` |
| Configuração | `fase4/config.py` | Carrega `.env` local com prioridade para variáveis já exportadas |

Veja [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para responsabilidades e
[docs/DATASETS.md](docs/DATASETS.md) para a política de dados, limites e fontes.
O replay está em [docs/REPLAY.md](docs/REPLAY.md) e as integrações de mídia
estão em [docs/MEDIA.md](docs/MEDIA.md). A configuração do Azure fica em
[docs/AZURE.md](docs/AZURE.md).

## ✅ Escopo implementado versus próximas etapas

| Funcionalidade | Situação |
|---|---|
| Banco novo, 25 pacientes fictícios e prescrições de teste | Implementado |
| Download limitado de fontes oficiais, hashes e validação | ✅ Implementado, com testes sem rede |
| Importação PhysioNet PSV / índice AudioSet CSV | ✅ Implementado |
| Separação de origens nas análises de sinais vitais | ✅ Implementado |
| Replay temporal hora a hora, sem olhar dados futuros | ✅ Implementado e testado |
| Revisão humana (revisado/descartado) | ✅ Implementado e testado |
| Inspeção local WAV (energia, baixa intensidade, saturação) | ✅ Implementado e testado sem Azure |
| Download do modelo MediaPipe Lite oficial | ✅ Download real validado; arquivo não versionado |
| Leitura de MP4, ângulos de joelhos/cotovelos | 🟡 Código testado com dublês; vídeo real a validar |
| Seleção de trechos AudioSet, importação WAV e treino com origem documentada | ✅ Código e testes locais implementados; WAVs reais externos a fornecer |
| Outliers de sinais vitais, postura e mudanças de prescrições | Implementado (experimental) |
| Camada de aplicação com portas e adaptadores | Implementada e testada |
| Entrada única e diagnóstico do ambiente | Implementados e testados |
| Leitura automática do `.env` local com proteção das chaves | ✅ Implementada e testada sem usar credenciais reais |
| Azure Speech/Language | 🟡 Código preparado; requer credenciais e teste real |
| MediaPipe Pose | 🟡 Modelo acessível; inferência com MP4 real pendente |
| Interface Streamlit e API HTTP | 🟡 Implementadas; teste com dependências completas pendente |
| Fusão de eventos no dashboard | ⏳ Planejada; função de domínio inicial disponível |
| Monitoramento contínuo / alertas em tempo real | ⏳ Pendente; replay é manual e histórico |
| Métricas com dados rotulados, relatório e vídeo final | ⏳ Pendentes |

## 🧪 Qualidade e privacidade

- `python -m unittest discover -s tests -v` testa a lógica e casos de uso com
  substitutos de Azure e MediaPipe, sem acessar serviços externos.
- A pasta `data/raw/`, os modelos `.task`, mídias enviadas e os arquivos SQLite
  não são versionados. Cópias temporárias de novos uploads são removidas após
  o processamento, mantendo os resultados/evidências no SQLite.
- Não é criado nenhum diagnóstico a partir de voz, sentimento ou postura.
- Alertas são encaminhados para `pending_review` e mostram evidências para
  revisão humana.
- O projeto não contém bancos ou código da Fase 3.

