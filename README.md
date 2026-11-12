# 🩺 Tech Challenge — Fase 4 | Monitoramento multimodal

**Versão 0.9.2 — instalação reproduzível no Windows, Azure Speech/Language, PhysioNet, MediaPipe e Streamlit.**

Protótipo acadêmico de monitoramento e alertas sobre **sinais vitais**, **prescrições e movimentação fictícias**, **áudio de consulta encenada** e **vídeo de movimentos**. Usa as fontes propostas na FIAP (**PhysioNet** e metadados do **Google AudioSet**) e as integrações **Azure Speech-to-Text**, **Azure AI Language** e **MediaPipe**.

> ⚠️ Apenas demonstração acadêmica. Não utilizar dados pessoais/consultas reais ou interpretar os alertas como diagnósticos. Não há monitoramento hospitalar em tempo real.

## 🚀 Comece aqui — primeiro uso no Windows 11

Execute **a partir da raiz do repositório**, onde está `pyproject.toml`. Escolha **Git Bash** *ou* **PowerShell**; não misture os comandos de ativação.

### 1. 🐍 Verificar o Python (obrigatório)

Recomendação: **Python 3.12 de 64 bits**. O `pyproject.toml` permite Python 3.12+, mas o projeto vinha sendo usado/testado no Windows com 3.12.10.

**Git Bash ou PowerShell:**

```bash
py -3.12 --version
py -3.12 -c "import struct; print('Arquitetura:', struct.calcsize('P') * 8, 'bits')"
```

Se `py` não existir, utilize `python --version` e `python -c "import struct; print(struct.calcsize('P') * 8)"`. Instale Python 3.12 x64 se necessário; não reaproveite um `.venv` criado com outra versão.

### 2. 📂 Entrar no projeto e criar `.venv` (somente no primeiro uso)

**Git Bash:**

```bash
cd /c/GITHUB/tech-challenge-fase4
py -3.12 -m venv .venv
source .venv/Scripts/activate
python --version
```

**PowerShell:**

```powershell
cd C:\GITHUB\tech-challenge-fase4
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

Se a política do PowerShell bloquear a ativação, rode `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` **somente nesse terminal** e repita a ativação. Alternativamente, use o Git Bash. Se `py` não estiver disponível, substitua `py -3.12 -m venv .venv` por `python -m venv .venv`, verificando antes a versão.

**Por quê?** O `.venv` isola as bibliotecas do projeto. Não é enviado ao GitHub. Nas próximas execuções, **apenas ative** o ambiente; não o recrie.

### 3. 📦 Instalar as bibliotecas e validar o gráfico (obrigatório)

Com o ambiente ativado, em **qualquer dos dois terminais**:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[all,test]"
python -m pip check
python -c "import sys, struct; print(sys.version); print('Python', struct.calcsize('P') * 8, 'bits')"
python -c "import pyarrow as pa; import altair; import streamlit; import pandas; print('Gráficos OK; PyArrow:', pa.__version__)"
```

| Comando | Para que serve |
|---|---|
| `pip install --upgrade pip` | Atualiza o instalador de bibliotecas do `.venv`. |
| `pip install -e ".[all,test]"` | Instala o app em modo editável e dependências de dashboard, vídeo, Azure, dados, API e testes. |
| `pip check` | Aponta incompatibilidades nas dependências instaladas. |
| `python -c "import pyarrow ..."` | **Verifica se o PyArrow e o Altair realmente carregam**; é o teste preventivo para o erro do gráfico de movimentação. |

**Critério de continuidade:** o comando de importação deve exibir `Gráficos OK`. Se falhar, **corrija antes de abrir o Streamlit**, seguindo [🩹 Solução de problemas no Windows](docs/SETUP_WINDOWS.md#-erro-ao-importar-pyarrowlib--dll-no-windows).

### 4. 🔐 Criar `.env` local (obrigatório apenas para usar Azure)

O `.env` **não deve ser versionado**. Se ainda não existe, no Git Bash execute `cp .env.example .env`; no PowerShell execute `Copy-Item .env.example .env`. **Não sobrescreva um `.env` que já possui suas chaves.**

Preencha **somente no computador local**:

```dotenv
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=brazilsouth
AZURE_LANGUAGE_KEY=
AZURE_LANGUAGE_ENDPOINT=https://language-tc4.cognitiveservices.azure.com/
FASE4_DB_PATH=data/fase4.sqlite3
```

- `AZURE_SPEECH_REGION`: deve conter **`brazilsouth`**, nunca `https://brazilsouth.api.cognitive.microsoft.com/`.
- `AZURE_LANGUAGE_ENDPOINT`: aqui **sim** deve haver uma URL do recurso Language.
- `AZURE_SPEECH_KEY` e `AZURE_LANGUAGE_KEY`: copiar do próprio Azure Portal. Nunca publicar ou compartilhar.
- `FASE4_DB_PATH`: arquivo SQLite local que o projeto cria automaticamente.
- `POSE_MODEL_PATH` pode ficar vazio: o padrão é `models/pose_landmarker_lite.task`.

**Atenção:** variáveis já exportadas no Windows/terminal têm prioridade sobre o `.env`. O `doctor` verifica presença das variáveis, **não** valida chave, acesso à rede ou cota.

### 5. 🩺 Inicializar o banco e conferir os dados fictícios (recomendado no primeiro uso)

```bash
python -m fase4 init
python -m fase4 patients
```

- `init`: cria o schema SQLite, 25 pacientes fictícios e cenários simulados de prescrições/movimento; é **idempotente**.
- `patients`: lista os casos fictícios e confirma que o banco abre.
- **Não é obrigatório executar `init` antes de `run`: o `run` também executa o `bootstrap()` automaticamente.**
- Não apague `data/fase4.sqlite3` se quiser preservar histórico de consultas e alertas.

### 6. 🧪 Testes automatizados e diagnóstico (recomendado)

```bash
python -m pytest -q
python -m fase4 doctor
```

- `pytest`: executa a suíte de regressão sem necessidade de chaves reais do Azure, MP4 ou downloads completos. Nesta atualização, **91 testes passaram no ambiente de revisão Linux**; ainda é necessário repetir no Windows.
- `doctor`: confere configuração e recursos locais. Nesta atualização, foram incluídos os campos **`pyarrow_runtime` e `altair_runtime`**: após instalar todas as dependências, o esperado é **`"ok"`**. Se aparecer `ausente` ou `falha ao importar`, corrija o ambiente antes de rodar a interface.
- `pose_model_configured: false` significa que o modelo MediaPipe ainda não foi baixado; **não impede abrir a interface**.
- `azure_*_configured: false` significa que o Azure ainda não foi configurado; **não impede abrir a interface**.

### 7. 📦 Baixar as fontes oficiais (somente para testar PhysioNet e AudioSet)

**Necessita de acesso à internet na primeira execução:**

```bash
python -m fase4 prepare-datasets
python -m fase4 validate-datasets
python -m fase4 import-physionet data/raw/official/p100679.psv --patient TC4-P001
```

| Comando | Para que serve |
|---|---|
| `prepare-datasets` | Baixa **um PSV PhysioNet** e **três CSVs de metadados AudioSet** para `data/raw/official/`, criando manifesto de proveniência. Não baixa áudio/vídeo do AudioSet. |
| `validate-datasets` | Verifica presença, estrutura, metadados e hashes dos quatro arquivos; não usa a internet. |
| `import-physionet ... --patient TC4-P001` | Importa uma série histórica pública para **um caso fictício de demonstração**. Permite gráficos de sinais vitais e replay. Reimportar o mesmo PSV não duplica medições. |

**Opcional:** `python -m fase4 audioset-preview data/raw/official/eval_segments.csv --limit 5` mostra cinco entradas dos metadados AudioSet. Nada disso é necessário para o primeiro carregamento do Streamlit.

### 8. 🎥 Baixar o modelo de vídeo (somente para análise MediaPipe)

```bash
python -m fase4 prepare-pose-model
```

Obtém o modelo público **MediaPipe Pose Landmarker Lite** em `models/pose_landmarker_lite.task` (download único, via internet). Se ele já está válido, o comando apenas o verifica. A falta do modelo **não afeta as abas de monitoramento/áudio**, mas impede analisar MP4 até ser preparado.

Para conferir um vídeo antes do upload:

```bash
python -m fase4 inspect-video "data/samples/videos/SEU_VIDEO.mp4"
```

Substitua `SEU_VIDEO.mp4` pelo nome de um arquivo realmente existente. O vídeo deve estar autorizado para uso. O aplicativo aceita **MP4 de até 60 MiB e 120 s**.

### 9. ▶️ Abrir o Streamlit

```bash
python -m fase4 run
```

O comando `run` inicializa o banco se necessário e abre o Streamlit. **Não** executa downloads do PhysioNet/MediaPipe nem treina modelos automaticamente. Abra o endereço local informado no terminal (geralmente `http://localhost:8501`).

**Nas próximas execuções**, bastam: entrar na pasta → ativar `.venv` → `python -m fase4 run`. Se modificar dependências, rode novamente `pip install -e ".[all,test]"` e `pip check`.

---

## ✅ Checklist: o que é necessário para cada funcionalidade?

| Funcionalidade | Obrigatório antes de utilizar | Desnecessário para abrir o Streamlit? |
|---|---|---|
| Interface e movimentação fictícia | Python, `.venv`, instalação completa, **PyArrow importável** | — |
| Casos fictícios e SQLite | `run` inicializa automaticamente; `init` é opcional | Sim, `init` separado |
| Sinais vitais e replay PhysioNet | `prepare-datasets`, `validate-datasets`, `import-physionet` | Sim |
| Áudio com Azure | Quatro variáveis do `.env`, WAV adequado e conectividade Azure | Sim |
| Vídeo MediaPipe | `prepare-pose-model` e MP4 compatível | Sim |
| Metadados Google AudioSet | `prepare-datasets` | Sim |
| Treinamento próprio de modelos | **Não é requisito para o fluxo principal** | Sim |

## 🧭 Como demonstrar as abas

1. **📦 Dados:** preparar/importar a amostra oficial, quando ainda não executado via terminal.
2. **🫀 Monitoramento:** selecionar `TC4-P001`, visualizar a trajetória simulada e analisar sinais vitais, prescrições e movimentação.
3. **⏯️ Replay:** iniciar/pausar a reprodução de sinais históricos PhysioNet, se uma série tiver sido importada.
4. **🎙️ Áudio + Azure:** enviar WAV fictício **PCM16, mono, 16 kHz (ou 8 kHz), até 30 s**; transcrever e conferir sentimento, expressões-chave, entidades, trechos do relato e alertas. É possível inspecionar o WAV localmente sem Azure.
5. **🎥 Vídeo:** enviar MP4 autorizado, analisar ângulos de joelhos/cotovelos e exportar relatório JSON.
6. **🚨 Alertas:** revisar evidências e correlação ilustrativa por caso e janela de 30 minutos; não representa simultaneidade clínica.

### Testes pela CLI (opcionais)

```bash
# WAV encenado já disponível no projeto
python -m fase4 inspect-wav data/samples/audios/0001_azure_16khz.wav --patient TC4-P001

# Requer Azure configurado e acesso aos serviços
python -m fase4 analyze-audio data/samples/audios/0001_azure_16khz.wav --patient TC4-P001

# Requer amostra PhysioNet importada para obter desvios vitais
python -m fase4 scan all --patient TC4-P001

# Alertas persistidos para o caso
python -m fase4 alerts --patient TC4-P001
```

No ZIP revisado, há áudios `OAW01...OAW05` convertidos para 16 kHz, mas algumas consultas completas **excedem 30 segundos**; utilize partes curtas em PCM16 mono antes de enviar ao Azure. Não presuma que um WAV já está dentro dos limites apenas porque termina em `.wav`.

## 🩹 Por que o Streamlit apresentou erro no PyArrow?

A aba **🫀 Monitoramento** executa `st.line_chart(frame.set_index("observed_at")[["x_m", "y_m"]])` em `fase4/interfaces/clinical_dashboard.py`. O Streamlit/Altair importa `pyarrow.lib` ao preparar os dados. No traceback compartilhado, o problema chega **à importação do PyArrow**, antes de indicar a exceção final. Assim, **não há evidência de que falte um dataset ou banco no GitHub**.

O `doctor` anterior só conferia se a biblioteca existia; agora verifica se **PyArrow e Altair podem ser importados**. Para erros de DLL/ambiente Windows, veja o diagnóstico e as alternativas de reparo em **[docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md#-erro-ao-importar-pyarrowlib--dll-no-windows)**. A [documentação oficial do Apache Arrow](https://arrow.apache.org/docs/python/install.html) recomenda conferir o Visual C++ Redistributable em falhas de importação no Windows.

## 📁 Organização e GitHub

- `fase4/domain/`: detecção de desvios e regras transparentes.
- `fase4/application/`: casos de uso e portas.
- `fase4/infrastructure/`: SQLite, PhysioNet, AudioSet, Azure, MediaPipe.
- `fase4/interfaces/`: CLI, Streamlit e API.
- `tests/`: regressão automatizada.
- `docs/`: preparação, arquitetura, fontes, relatório e testes.
- `data/samples/`: **opcionalmente versionar** exemplos pequenos, fictícios e com permissão de redistribuição.

O `.gitignore` deve manter **`.env`, `.venv/`, `data/raw/`, o SQLite local, uploads e modelos gerados** fora do Git. O ZIP recebido nesta revisão incluía mídia de teste, SQLite e a pasta interna `.git/`; **esses arquivos não são pré-requisitos para a correção do PyArrow**. Não distribua um ZIP com `.git/`, bases pessoais ou arquivos sem licença clara. Para verificar o que está no commit: `git status --short` e `git ls-files data models`.

## 📚 Documentação

- [🪟 Preparação completa e correção de falhas no Windows](docs/SETUP_WINDOWS.md)
- [📦 PhysioNet, AudioSet e proveniência](docs/DATASETS.md)
- [🔐 Configuração do Azure](docs/AZURE.md)
- [🎥 Processamento de áudio/vídeo](docs/MEDIA.md)
- [🧭 Arquitetura](docs/ARCHITECTURE.md)
- [✅ Matriz de requisitos](docs/REQUIREMENTS.md)
- [🧪 Plano de testes 0.9.2](docs/TEST_PLAN_v0.9.2.md)
- [📄 Relatório técnico](docs/TECHNICAL_REPORT.md)
- [🎬 Roteiro de entrega (até 15 min)](docs/DEMO_SCRIPT.md)

**Limites:** os testes automatizados usam substitutos para serviços Azure e processamento de vídeo. É indispensável validar no Windows a importação do PyArrow, um MP4 real e uma chamada Azure real. Não há avaliação de eficácia clínica.
