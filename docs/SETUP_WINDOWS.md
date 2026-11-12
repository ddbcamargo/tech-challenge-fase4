# 🪟 Guia de instalação, pré-requisitos e diagnóstico — Windows 11

Esta referência complementa o [README da raiz](../README.md). Os comandos abaixo foram conferidos contra `fase4/interfaces/cli.py` da versão 0.9.2. Em especial, **não é necessário baixar PhysioNet ou MediaPipe para abrir o Streamlit**; esses passos habilitam partes específicas da demonstração.

## 🧰 Mapa dos comandos existentes

| Comando | Depende de | Finalidade | Quando executar |
|---|---|---|---|
| `py -3.12 -m venv .venv` | Python 3.12 instalado | Cria ambiente isolado | Apenas primeiro uso |
| `source .venv/Scripts/activate` | Git Bash e `.venv` existente | Ativa Python local | A cada novo Git Bash |
| `.\.venv\Scripts\Activate.ps1` | PowerShell e `.venv` existente | Ativa Python local | A cada novo PowerShell |
| `python -m pip install -e ".[all,test]"` | `.venv` ativado | Instala dependências de dashboard, Azure, API, vídeos, testes etc. | Primeiro uso ou alterações no ambiente |
| `python -m pip check` | Dependências instaladas | Procura incompatibilidades declaradas | Após instalar/reparar |
| `python -c "import pyarrow; import altair; import streamlit"` | Dashboard instalado | Verifica os imports exigidos pelo gráfico | **Antes de executar o app** |
| `python -m pytest -q` | Extras `test` instalados | Executa testes unitários | Antes da entrega; após mudanças |
| `python -m fase4 doctor` | Projeto instalado | Diagnóstico sem acessar Azure | Antes da primeira execução |
| `python -m fase4 init` | Projeto instalado | Cria SQLite, pacientes fictícios, prescrições e movimento; idempotente | Opcional: o `run` também faz |
| `python -m fase4 patients` | Banco inicializado | Lista os 25 casos fictícios | Para confirmar bootstrap |
| `python -m fase4 prepare-datasets` | Internet | Baixa PSV PhysioNet + 3 CSVs AudioSet, com manifesto | Antes de testar PhysioNet/AudioSet |
| `python -m fase4 validate-datasets` | Dados oficiais baixados | Verifica hashes, integridade e estrutura | Depois de `prepare-datasets` |
| `python -m fase4 import-physionet data/raw/official/p100679.psv --patient TC4-P001` | PSV disponível, banco inicializado | Vincula série histórica a um caso fictício | Antes do replay/gráficos vitais |
| `python -m fase4 prepare-pose-model` | Internet | Baixa MediaPipe Pose Landmarker Lite | Antes de analisar MP4 |
| `python -m fase4 inspect-video "CAMINHO/VIDEO.mp4"` | OpenCV instalado, MP4 existente | Verifica metadados do vídeo | Opcional para diagnosticar MP4 |
| `python -m fase4 inspect-wav "CAMINHO/AUDIO.wav"` | WAV existente | Inspeção acústica local; sem Azure | Opcional |
| `python -m fase4 analyze-audio "CAMINHO/AUDIO.wav" --patient TC4-P001` | WAV curto + Azure configurado | Speech + Language + persistência | Teste real do Azure |
| `python -m fase4 scan all --patient TC4-P001` | Banco preparado | Analisa sinais, prescrições, movimento e alertas | Opcional pela CLI |
| `python -m fase4 alerts --patient TC4-P001` | Banco preparado | Consulta alertas persistidos | Opcional pela CLI |
| `python -m fase4 run` | Pacotes do dashboard funcionando | Inicializa banco e abre Streamlit | Para usar a aplicação |
| `python -m fase4 api` | FastAPI/uvicorn instalados | Sobe API FastAPI, não o Streamlit | Alternativo, não obrigatório |

**Não é necessário executar comandos de treinamento de modelos.** Comandos adicionais da CLI sobre curadoria AudioSet existem para exploração separada do fluxo principal.

## ⚡ Instalação inicial — sequência sugerida

No **Git Bash**:

```bash
cd /c/GITHUB/tech-challenge-fase4
py -3.12 --version
py -3.12 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e ".[all,test]"
python -m pip check
python -c "import pyarrow as pa; import altair; import streamlit; print('OK:', pa.__version__)"
python -m pytest -q
python -m fase4 doctor
python -m fase4 init
python -m fase4 run
```

`init` é para validar a primeira inicialização; o `run` já cria o banco de maneira idempotente. Se o projeto for apenas demonstrado sem séries oficiais, pode parar por aqui e abrir o Streamlit.

Para **habilitar as bases e o vídeo**, faça adicionalmente, **antes ou depois de abrir** o app:

```bash
python -m fase4 prepare-datasets
python -m fase4 validate-datasets
python -m fase4 import-physionet data/raw/official/p100679.psv --patient TC4-P001
python -m fase4 prepare-pose-model
```

Essas operações podem fazer downloads externos; não tente resolvê-las alterando permissões da pasta `.venv` ou inserindo arquivos binários no GitHub.

## 🩹 Erro ao importar `pyarrow.lib` / DLL no Windows

### Sintoma confirmado no código

A aba `🫀 Monitoramento` chama, em `fase4/interfaces/clinical_dashboard.py`:

```python
st.line_chart(frame.set_index("observed_at")[["x_m", "y_m"]])
```

O Streamlit e o Altair transformam o DataFrame e importam `pyarrow`. No traceback fornecido, o erro atinge `pyarrow.__init__` / `pyarrow.lib`. **Não foi fornecida a última linha da exceção**, portanto não é possível afirmar se foi DLL ausente, instalação corrompida ou incompatibilidade. **O SQLite, a pasta `data/` e o modelo MediaPipe não são a causa desse ponto de falha.**

### 1. Identifique qual Python está sendo usado

No PowerShell, com o `.venv` ativado:

```powershell
cd C:\GITHUB\tech-challenge-fase4
.\.venv\Scripts\Activate.ps1
Get-Command python
python -c "import sys, struct; print(sys.executable); print(sys.version); print(struct.calcsize('P')*8, 'bits')"
python -m pip --version
python -m pip check
```

Esperado: `sys.executable` termina em `.venv\Scripts\python.exe`; Python 3.12 **64 bits** é recomendado.

### 2. Teste isoladamente o PyArrow

```powershell
python -c "import pyarrow as pa; print(pa.__version__)"
python -c "import altair, streamlit, pandas; print('Dashboard OK')"
python -m fase4 doctor
```

No `doctor` atualizado, verifique `pyarrow_runtime` e `altair_runtime`:

- `ok`: importação validada nesse ambiente.
- `ausente`: pacote não instalado no `.venv` ativo.
- `falha ao importar (ImportError/...)`: biblioteca presente, mas com erro de importação; observe a mensagem.

### 3. Se o PyArrow não importar

Tente, nesta ordem, **sem recriar o banco de dados**:

```powershell
python -m pip install --force-reinstall --no-cache-dir --no-deps pyarrow
python -m pip check
python -c "import pyarrow as pa; print('PyArrow OK:', pa.__version__)"
```

A opção `--no-deps` reinstala apenas o PyArrow, evitando mudanças acidentais nos demais pacotes. Se a mensagem final indicar **DLL load failed**, instale/repare o **Microsoft Visual C++ Redistributable x64** pelo link oficial: <https://aka.ms/vc14/vc_redist.x64.exe>. Depois feche e reabra o terminal e repita o import. A [documentação do Apache Arrow](https://arrow.apache.org/docs/python/install.html) faz essa recomendação para problemas com wheels no Windows.

Se persistir, execute `python -m pip show pyarrow streamlit altair numpy pandas` e guarde o **traceback inteiro, incluindo a última linha**. Não publique o `.env`.

### 4. Última opção: recriar somente `.venv`

**Apenas se as tentativas acima falharem**. Desative/feche o Streamlit primeiro. O procedimento não apaga o `.env`, a pasta `data/`, `models/` nem o SQLite.

```powershell
deactivate
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[all,test]"
python -m pip check
python -c "import pyarrow as pa; print('PyArrow OK:', pa.__version__)"
python -m fase4 doctor
python -m fase4 run
```

Não apague `.venv` com a aplicação em execução. **Não precisa reclonar o projeto** para resolver uma DLL do ambiente local.

## 🧱 Erros diferentes: como distinguir

| Mensagem/sintoma | O que verificar | Correção típica |
|---|---|---|
| `ModuleNotFoundError: streamlit` | `.venv` ativo, `pip install -e ".[all,test]"` | Instalar extras no Python correto |
| `pyarrow.lib`, `DLL load failed` | Import isolado, runtime Visual C++, instalação do wheel | Seção anterior |
| `pose_model_configured: false` | Arquivo `.task` local | `prepare-pose-model`, só para vídeo |
| PhysioNet ausente / replay vazio | `data/raw/official` + importação PSV | `prepare-datasets`, `validate-datasets`, `import-physionet` |
| Azure Speech retorna falha | `AZURE_SPEECH_REGION` deve ser o código regional (`brazilsouth`) | Ajustar `.env` local, reiniciar |
| Azure Language falha | Chave/endpoint e acesso ao serviço | Conferir Azure Portal, sem mostrar chaves |
| Gravação WAV recusada | Codec, canais, taxa, duração | WAV PCM16 mono 8/16 kHz, até 30 s |
| MP4 recusado | Codec, resolução, tamanho e duração | MP4 autorizado até 60 MiB/120 s |

## 🔐 Repositório e arquivos de dados

- **Versionar**: código, `README.md`, `docs/`, `tests/`, `pyproject.toml`, `.env.example` sem segredos, exemplos pequenos **com direitos de redistribuição**.
- **Não versionar**: `.env`, `.venv`, `data/fase4.sqlite3` e auxiliares, `data/raw`, uploads temporários, cache, vídeos/áudios de terceiros sem licença.
- O `.gitignore` não impede um arquivo **já rastreado** de continuar no Git. Verifique `git ls-files data models` e `git status --short` antes de publicar.
- A ausência do arquivo SQLite no repositório **é esperada**: `init` e `run` o criam. A ausência das amostras oficiais também é esperada se os comandos de preparação estiverem documentados.

## 🔁 Execuções seguintes

**Git Bash:** `cd /c/GITHUB/tech-challenge-fase4 && source .venv/Scripts/activate && python -m fase4 run`.

**PowerShell:** entre na raiz, execute `.\.venv\Scripts\Activate.ps1` e depois `python -m fase4 run`.

Não repita os downloads toda vez: o PhysioNet/AudioSet e o modelo MediaPipe são preparados uma vez. Para atualizar dependências, instale novamente o projeto e execute `pip check` e o teste de importação do PyArrow.
