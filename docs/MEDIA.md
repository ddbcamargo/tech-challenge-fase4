# 🎙️🎥 Etapa 0.5 — áudio e vídeo

## O que esta etapa entrega

1. **WAV local, sem conta Azure:** leitura técnica de arquivos PCM 16-bit,
   duração, taxa, intensidade média (dBFS), envelope, fração de baixa energia
   e amostras saturadas. O gráfico pode ser aberto no Streamlit.
2. **Azure Speech + Language, opcional:** o mesmo WAV curto pode ser transcrito
   e o texto analisado se as credenciais estiverem configuradas.
3. **Vídeo MP4:** inspeção de metadados e preparação idempotente do modelo
   Google MediaPipe Lite `.task`; a análise usa o modelo para estimar ângulos
   de joelhos e cotovelos nos quadros amostrados.
4. **AudioSet:** o painel mostra exemplos de registros públicos rotulados
   como `Speech`/`Conversation`. São índices, não transcrições de consultas.

## Fluxo no Git Bash (Windows)

```bash
cd /c/GITHUB/tech-challenge-fase4
source .venv/Scripts/activate
python -m pip install -e ".[all,test]"
python -m fase4 doctor
python -m fase4 run
```

Na aba **🎙️ 3. Áudio**, envie um WAV e clique **Inspecionar WAV localmente**.
Na aba **🎥 4. Vídeo**, clique em **Preparar modelo MediaPipe Lite**, envie o
vídeo e clique em **Analisar postura**.

Os novos botões não executam ações externas ao abrir o painel. A preparação
do modelo é um download **somente após clique**, pela URL oficial:

https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker

O modelo fica em `models/pose_landmarker_lite.task` (fora do Git). Se quiser
fornecer outro arquivo `.task` compatível, defina a variável `POSE_MODEL_PATH`
no seu sistema. O código verifica que o pacote contém os dois modelos de
detecção de postura esperados.

## Preparando áudio encenado

**Nunca use gravações reais de pacientes sem autorização e tratamento adequado
da privacidade.** Para a demonstração, grave uma consulta fictícia de 10 a 20
segundos, com autorização da pessoa que fala, por exemplo:

> "Esta é uma consulta fictícia usada em um projeto acadêmico. Hoje me senti
> cansado após caminhar. Gostaria de conversar sobre meu acompanhamento."

Formato recomendado:

| Propriedade | WAV para Azure |
|---|---|
| Codec | PCM linear, 16 bits |
| Canais | 1 (mono) |
| Taxa | 16.000 Hz (ou 8.000 Hz) |
| Duração | Até 30 segundos no reconhecimento de uma fala |

Para converter, caso já tenha o FFmpeg instalado:

```bash
ffmpeg -i entrada.m4a -ac 1 -ar 16000 -c:a pcm_s16le data/raw/consulta_encenada.wav
```

O inspetor **local** aceita também WAV estéreo PCM16, mas informa quando o
formato deve ser ajustado antes de enviar ao Azure. WAVs locais são limitados
a 90 segundos e 16 MiB.

Se configurar Azure, preencha localmente estas variáveis no arquivo `.env`
da raiz do projeto (não versioná-las):

- `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`;
- `AZURE_LANGUAGE_KEY`, `AZURE_LANGUAGE_ENDPOINT`.

Desde a versão 0.6, o projeto carrega automaticamente `.env` via
`python-dotenv` quando inicia pela CLI, Streamlit ou API, sem substituir
valores já exportados no terminal. O passo a passo está em [AZURE.md](AZURE.md).
O Azure Speech usa reconhecimento de fala curta; sessões de
várias falas exigem outro modo de transcrição. A análise textual retorna
sentimento e entidades, **não detecta disartria, fadiga ou alteração de voz**.

## Preparando vídeo

- Use MP4 curto, até 60 MiB e dois minutos.
- Mostre uma pessoa claramente visível, com iluminação estável, para melhor
  chance de estimativa postural.
- Você pode encenar movimentos de fisioterapia com consentimento. Não use
  imagens clínicas reais de terceiros sem autorização.
- O modelo analisa os quadros amostrados a cada cinco frames e extrai quatro
  articulações: `left_knee`, `right_knee`, `left_elbow`, `right_elbow`.
- Se não detectar pessoa ou não houver amostras suficientes, o painel avisa.

O enunciado não oferece uma base específica de vídeos. O candidato acadêmico
KIMORE contém exercícios de reabilitação, mas os pesquisadores indicam
solicitação de acesso aos **vídeos RGB**; não vamos redistribuí-los ou assumir
licença de uso sem confirmação: https://doi.org/10.1109/TNSRE.2019.2923060

## Arquitetura e privacidade

| Componente | Responsabilidade |
|---|---|
| `domain/acoustics.py` | Calcula descritores numéricos do sinal PCM |
| `infrastructure/wav.py` | Lê WAV e impõe limites de tamanho/formato |
| `infrastructure/pose_model.py` | Baixa e verifica o modelo do Google |
| `infrastructure/pose.py` | Extrai frames e estima juntas com MediaPipe |
| `application/service.py` | Processa casos de uso e persiste resultados |
| `interfaces/dashboard_sections.py` | Exibe upload, player, gráficos e botões |

Os arquivos brutos enviados ao painel são copiados temporariamente e removidos
ao finalizar sua operação. Dados resumidos (e, quando Azure é acionado,
**transcrições**) podem permanecer em `data/fase4.sqlite3`. Trate esse banco
como dado sensível se optar por usar gravações reais; no trabalho acadêmico,
prefira encenações.

## Verificações técnicas

```bash
python -m fase4 prepare-pose-model
python -m fase4 inspect-wav data/raw/consulta_encenada.wav --patient TC4-P001
python -m fase4 inspect-video data/raw/fisioterapia.mp4
python -m unittest discover -s tests -v
```

Os dois comandos `inspect-*` precisam dos arquivos locais informados. Os
testes automatizados não consomem Azure nem fazem downloads externos. O
download real do `.task` oficial foi verificado durante o desenvolvimento;
**a inferência em um MP4 real e chamadas Azure reais ainda precisam ser
validadas no ambiente da equipe**.
