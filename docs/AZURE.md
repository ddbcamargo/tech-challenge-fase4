# 🔐 Integração Azure Speech + Language — Fase 4

## ✅ Recursos já criados no portal

| Recurso Azure | Nome | Aplicação no desafio |
|---|---|---|
| 🎙️ Azure AI Speech | `speech-tc4` | Transcrever consulta fictícia (WAV curto) |
| 📝 Azure AI Language / Text Analytics | `language-tc4` | Sentimentos, frases-chave e entidades do texto |

Ambos foram criados na assinatura `Azure subscription 1`, grupo
`rg-tech-challenge-fase4`, região `Brazil South` (`brazilsouth`) e plano
**Free F0**. Esses recursos existem no portal do usuário; **nenhuma chamada
real foi executada durante os testes automatizados do projeto**.

## 🪟 Configurar no Windows Git Bash

Entre na raiz do projeto e ative o ambiente virtual existente:

```bash
cd /c/GITHUB/tech-challenge-fase4
source .venv/Scripts/activate
```

**Somente se ainda não existir `.env`**, crie uma cópia do modelo:

```bash
cp .env.example .env
```

Abra o arquivo local para preencher os valores do portal:

```bash
notepad .env
```

As variáveis do `.env` são:

```dotenv
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=brazilsouth
AZURE_LANGUAGE_KEY=
AZURE_LANGUAGE_ENDPOINT=https://language-tc4.cognitiveservices.azure.com/
```

- **`AZURE_SPEECH_KEY`:** copie a `CHAVE 1` de `speech-tc4`.
- **`AZURE_SPEECH_REGION`:** identificador regional exibido no Speech, `brazilsouth`.
- **`AZURE_LANGUAGE_KEY`:** copie a `CHAVE 1` de `language-tc4`.
- **`AZURE_LANGUAGE_ENDPOINT`:** copie exatamente o `Ponto final` do Language.

As linhas acima com as chaves vazias são **apenas instruções**: coloque os
valores reais **somente no seu `.env` local**. Não os envie à conversa,
commits, prints, tickets ou logs. **Não use o botão “Regenerar chave”** durante
a configuração inicial. O `.env.example` deve permanecer vazio.

O arquivo `.gitignore` já contém `.env`; confirme no Git Bash:

```bash
git check-ignore .env
```

O resultado esperado é `.env`. Se não aparecer, pare antes de usar `git add`.
O arquivo `.env` também **não acompanha o ZIP** distribuído do projeto.

## ▶️ Instalar atualização e executar

Para receber `python-dotenv` como dependência da versão 0.7:

```bash
python -m pip install -e ".[all,test]"
python -m fase4 doctor
```

O diagnóstico deve indicar:

```json
{
  "azure_speech_configured": true,
  "azure_language_configured": true
}
```

Essas são **duas propriedades dentro da saída maior**, não a resposta inteira.
Elas significam somente que as variáveis estão presentes: **não validam
conectividade, chave, faturamento ou funcionamento real do Azure**.

Depois, inicie o dashboard normalmente:

```bash
python -m fase4 run
```

Na aba **🎙️ 3. Áudio**, envie uma gravação **encenada/consentida** de até 30 s,
WAV **mono PCM16 16 kHz**. Primeiro clique em **Inspecionar WAV localmente**;
em seguida, clique em **☁️ Transcrever e analisar com Azure**, quando disponível.
A transcrição e a análise textual serão chamadas nos serviços criados.

## 🛡️ Como funciona o carregamento e a segurança

- `fase4/config.py` lê **somente** o `.env` da raiz do projeto, sem depender
  da pasta atual do terminal. O arquivo é lido na CLI e no ponto de composição
  usado por Streamlit/API.
- O carregamento usa `python-dotenv` com `override=False`: variáveis já
  definidas no terminal ou no servidor continuam com prioridade.
- O `doctor` não revela chaves; também não envia qualquer requisição externa.
- Não guarde consultas de pacientes reais sem base legal, consentimento e
  controles adequados. O protótipo não faz diagnóstico de disartria ou fadiga.
- A transcrição e os resultados derivados podem ficar registrados no SQLite;
  prefira dados sintéticos. Não use dados reais para testes acadêmicos.
- Se precisar revogar uma chave vazada, faça a rotação pelo portal Azure e
  atualize somente o seu `.env` local.

Os recursos Free F0 têm cotas de uso. Verifique os limites atuais no portal
antes de executar testes extensos; alertas de orçamento são úteis, mas não
substituem limites de acesso e uso.

## ☁️ Etapa 0.7 — histórico persistido e diagnóstico

O botão **☁️ Transcrever e analisar com Azure** chama, nesta ordem:

1. `ApplicationService.process_audio()` — valida WAV mono, PCM16, 8/16 kHz,
   limite de 30 segundos e configurações locais.
2. `AzureSpeechAndLanguage.transcribe()` — `SpeechRecognizer.recognize_once_async()`
   para **uma fala curta**, não uma consulta completa com vários turnos.
3. `AzureSpeechAndLanguage.analyze()` — `analyze_sentiment`,
   `extract_key_phrases` e `recognize_entities` com o Azure Language.
4. `SqlitePatientStore.save_media_event()` — grava a transcrição, o sentimento,
   os termos e a proveniência **somente após as duas integrações concluírem**.
5. `SqlitePatientStore.media_events()` — consulta eventos gravados, sem reenviar
   texto ou áudio ao Azure. O painel exibe isso em **📋 Histórico de análises Azure**.

O projeto **não grava arquivos WAV brutos** no banco: uploads temporários são
excluídos após a ação. Entretanto, **o texto da transcrição permanece no SQLite**,
por isso use somente narrativas fictícias. A associação com pacientes fictícios
não afirma que os registros públicos sejam dessas pessoas.

### ⌨️ Smoke test real pelo Git Bash

```bash
python -m fase4 doctor
python -m fase4 inspect-wav data/raw/consulta_encenada.wav --patient TC4-P001
python -m fase4 analyze-audio data/raw/consulta_encenada.wav --patient TC4-P001
```

A primeira linha confere a presença das configurações (não a sua validade).
A segunda mede o WAV localmente, sem nuvem. A terceira faz chamadas reais e
salva o resultado, consumindo a cota F0. A CLI imprime apenas contagens,
sentimento e termos literais; o conteúdo da transcrição fica no histórico do
Streamlit. **Cada repetição dessa última chamada consome a franquia de novo.**

### Erros típicos

| Mensagem | Como agir |
|---|---|
| Configuração ausente no `.env` | Confira as quatro variáveis e reinicie o app |
| Nenhuma fala foi reconhecida | Grave uma fala clara em pt-BR e valide mono 16 kHz |
| Azure Speech cancelou o reconhecimento | Verifique chave, região `brazilsouth`, plano e conectividade |
| Falha na chamada Language | Verifique `language-tc4`, endpoint HTTPS, chave e limites |

Para testes e evidências de aprovação, utilize
[AZURE_VALIDATION.md](AZURE_VALIDATION.md).

Fontes: [Reconhecimento de fala — Microsoft Learn](https://learn.microsoft.com/pt-br/azure/ai-services/speech-service/how-to-recognize-speech)
 e [Text Analytics Python SDK](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-textanalytics-readme?view=azure-python).

## 📝 Apresentação da transcrição no Streamlit — v0.9.2

Na aba **Áudio + Azure** a análise é exibida em campos separados: transcrição,
sentimento (com níveis de confiança quando fornecidos pelo SDK), expressões-chave,
entidades, trechos textuais para revisão humana e indicadores acústicos locais.

Os trechos para revisão são encontrados por regras próprias do domínio e preservam
o texto e os offsets originais. Não se deve atribuir esses trechos ao modelo Azure.
Os alertas ficam vinculados à análise de áudio por `media_event_id` e ao caso
fictício pelo `patient_id`. O histórico é lido do SQLite sem nova chamada de rede.
